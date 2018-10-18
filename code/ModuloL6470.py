__author__ = "Leandro1993"

"""Python 2.7 script controller for L6470 motor driver module develop by Leandro Mayrata as a part of his final project degree.
Source Refrence: https://github.com/ameyer/Arduino-L6470/blob/master/L6470/L6470.cpp and 'MangoKid' script used in SlushEngine project
"""
import RPi.GPIO as gpio
import L6470_Reg as LReg
import spidev as spidev
import time
import os
import sys
import math

class L6470:
	def __init__(Pin_RST,Pin_CE):
		self.chipSelect = Pin_CE
		self.RST = Pin_CE
		self.initGPIOState()
		self.initSPI()
		
		
		if (self.getParam(LReg.CONFIG) == 0x2e88):
            print "Motor Drive Connected on GPIO"
		else:
			print "Error de coneccion SPI"
		
		
	def initGPIOState(self, Pin_RST, Pin_CE):
		gpio.setmode(gpio.BCM)
		gpio.setup(self.RST, gpio.OUT)
		gpio.setup(self.chipSelect, gpio.OUT)
		gpio.output(self.chipSelect, gpio.HIGH)
		
		gpio.output(self.RST, gpio.LOW)
		time.sleep(.1)
		gpio.output(self.RST, gpio.HIGH)    
		time.sleep(.1)
		
	
	def initSPI(self):
	    spi = spidev.SpiDev()
		spi.open(0,0)
		spi.max_speed_hz = 100000
		spi.bits_per_word = 8
		spi.loop = False
		spi.mode = 3
	
	def isBusy(self):
		status = self.getStatus()
        return (not ((status >> 1) & 0b1))
    
    ''' wait for motor to finish moving'''
    def waitMoveFinish(self):
        status = 1
        while status:
            status = self.getStatus()
            status = not((status >> 1) & 0b1)

    ''' set the microstepping level '''
    def setMicroSteps(self, microSteps):
        self.free()
        stepVal = 0

        for stepVal in range(0, 8):
            if microSteps == 1:
                break
            microSteps = microSteps >> 1;
            
        self.setParam(LReg.STEP_MODE, (0x00 | stepVal | LReg.SYNC_SEL_1))

    ''' set the threshold speed of the motor '''
    def setThresholdSpeed(self, thresholdSpeed):
        if thresholdSpeed == 0:
            self.setParam(LReg.FS_SPD, 0x3ff)
        else:
            self.setParam(LReg.FS_SPD, self.fsCalc(thresholdSpeed))

    ''' set the current'''
    def setCurrent(self, hold, run, acc, dec):
        self.setParam(LReg.KVAL_RUN, run)
        self.setParam(LReg.KVAL_ACC, acc)
        self.setParam(LReg.KVAL_DEC, dec)
        self.setParam(LReg.KVAL_HOLD, hold)

    '''set the maximum motor speed'''
    def setMaxSpeed(self, speed):
        self.setParam(LReg.MAX_SPEED, self.maxSpdCalc(speed))

    ''' set the minimum speed '''
    def setMinSpeed(self, speed):
        self.setParam(LReg.MIN_SPEED, self.minSpdCalc(speed))

    ''' set accerleration rate '''
    def setAccel(self, acceleration):
        accelerationBytes = self.accCalc(acceleration)
        self.setParam(LReg.ACC, accelerationBytes)

    ''' set the deceleration rate '''
    def setDecel(self, deceleration):
        decelerationBytes = self.decCalc(deceleration)
        self.setParam(LReg.DEC, decelerationBytes)

    ''' get the posistion of the motor '''
    def getPosition(self):
        return self.convert(self.getParam(LReg.ABS_POS))

    ''' get the speed of the motor '''
    def getSpeed(self):
        return self.getParam(LReg.SPEED)

    ''' set the overcurrent threshold '''
    def setOverCurrent(self, ma_current):
        OCValue = math.floor(ma_current/375)
        if OCValue > 0x0f: OCValue = 0x0f
        self.setParam((LReg.OCD_TH), OCValue)

    ''' set the stall current level '''
    def setStallCurrent(self, ma_current):
        STHValue = round(math.floor(ma_current/31.25))
        if(STHValue > 0x80): STHValue = 0x80
        if(STHValue < 0): STHValue = 9
        self.setParam((LReg.STALL_TH), STHValue)

    ''' set low speed optamization '''
    def setLowSpeedOpt(self, enable):
        self.xfer(LReg.SET_PARAM | LReg.MIN_SPEED[0])
        if enable: self.param(0x1000, 13)
        else: self.param(0, 13)

    ''' start the motor spinning '''
    def run(self, dir, spd):
        speedVal = self.spdCalc(spd)
        self.xfer(LReg.RUN | dir)
        if speedVal > 0xfffff: speedVal = 0xfffff
        self.xfer(speedVal >> 16)
        self.xfer(speedVal >> 8)
        self.xfer(speedVal)

    ''' sets the clock source '''
    def stepClock(self, dir):
        self.xfer(LReg.STEP_CLOCK | dir)

    ''' move the motor a number of steps '''
    def move(self, nStep):
        dir = 0

        if nStep >= 0:
            dir = LReg.FWD
        else:
            dir = LReg.REV

        n_stepABS = abs(nStep)

        self.xfer(LReg.MOVE | dir)
        if n_stepABS > 0x3fffff: nStep = 0x3fffff
        self.xfer(n_stepABS >> 16)
        self.xfer(n_stepABS >> 8)
        self.xfer(n_stepABS)

    ''' move to a position with refrence to the motors current position '''
    def goTo(self, pos):
        self.xfer(LReg.GOTO)
        if pos > 0x3fffff: pos = 0x3fffff
        self.xfer(pos >> 16)
        self.xfer(pos >> 8)
        self.xfer(pos)

    ''' same as go to but with a forced direction '''
    def goToDir(self, dir, pos):
        self.xfer(LReg.GOTO_DIR)
        if pos > 0x3fffff: pos = 0x3fffff
        self.xfer(pos >> 16)
        self.xfer(pos >> 8)
        self.xfer(pos)

    ''' go until switch press event occurs '''
    def goUntilPress(self, act, dir, spd):
        self.xfer(LReg.GO_UNTIL | act | dir)
        if spd > 0x3fffff: spd = 0x3fffff
        self.xfer(spd >> 16)
        self.xfer(spd >> 8)
        self.xfer(spd)

    ''' go until switch release event occurs '''
    def goUntilRelease(self, act, dir):
        self.xfer(LReg.RELEASE_SW | act | dir)

    ''' go home '''
    def goHome(self):
        self.xfer(LReg.GO_HOME)

    ''' go to mark position '''
    def goMark(self):
        self.xfer(LReg.GO_MARK)

    ''' set mark point '''
    def setMark(self, value):

        if value == 0: value = self.getPosition()
        self.xfer(LReg.MARK)
        if value > 0x3fffff: value = 0x3fffff
        if value < -0x3fffff: value = -0x3fffff

        self.xfer(value >> 16)
        self.xfer(value >> 8)
        self.xfer(value)

    ''' set current position to the home position '''
    def setAsHome(self):
        self.xfer(LReg.RESET_POS)

    ''' reset the device to initial conditions '''
    def resetDev(self):
        self.xfer(LReg.RESET_DEVICE)

    ''' stop the motor using the decel '''
    def softStop(self):
        self.xfer(LReg.SOFT_STOP)

    ''' hard stop the motor without concern for decel curve '''
    def hardStop(self):
        self.xfer(LReg.HARD_STOP)

    ''' decelerate the motor and the disable hold '''
    def softFree(self):
        self.xfer(LReg.SOFT_HIZ)

    ''' disable hold '''
    def free(self):
        self.xfer(LReg.HARD_HIZ)

    ''' get the status of the motor '''
    def getStatus(self):
        temp = 0;
        self.xfer(LReg.GET_STATUS)
        temp = self.xfer(0) << 8
        temp += self.xfer(0)
        return temp

    ''' calculates the value of the ACC register '''
    def accCalc(self, stepsPerSecPerSec):
        temp = float(stepsPerSecPerSec) * 0.137438
        if temp > 4095.0: return 4095
        else: return round(temp)

    ''' calculated the value of the DEC register '''
    def decCalc(self, stepsPerSecPerSec):
        temp = float(stepsPerSecPerSec) * 0.137438
        if temp > 4095.0: return 4095
        else: return round(temp)

    ''' calculates the max speed register '''
    def maxSpdCalc(self, stepsPerSec):
        temp = float(stepsPerSec) * 0.065536
        if temp > 1023.0: return 1023
        else: return round(temp)

    ''' calculates the min speed register '''
    def minSpdCalc(self, stepsPerSec):
        temp = float(stepsPerSec) * 4.1943
        if temp > 4095.0: return 4095
        else: return round(temp)

    ''' calculates the value of the FS speed register '''
    def fsCalc(self, stepsPerSec):
        temp = (float(stepsPerSec) * 0.065536) - 0.5
        if temp > 1023.0: return 1023
        else: return round(temp)

    ''' calculates the value of the INT speed register '''
    def intSpdCalc(self, stepsPerSec):
        temp = float(stepsPerSec) * 4.1943
        if temp > 16383.0: return 16383
        else: return round(temp)

    ''' calculate speed '''
    def spdCalc(self, stepsPerSec):
        temp = float(stepsPerSec) * 67.106
        if temp > float(0x000fffff): return 0x000fffff
        else: return round(temp)

    ''' utility function '''
    def param(self, value, bit_len):
        ret_value = 0

        byte_len = bit_len/8
        if (bit_len%8 > 0): byte_len +=1

        mask = 0xffffffff >> (32 - bit_len)
        if value > mask: value = mask

        if byte_len >= 3.0:
            temp = self.xfer(value >> 16)
            ret_value |= temp << 16
        if byte_len >= 2.0:
            temp = self.xfer(value >>8)
            ret_value |= temp << 8
        if byte_len >= 1.0:
            temp = self.xfer(value)
            ret_value |= temp
       
        return (ret_value & mask)

    ''' transfer data to the spi bus '''
    def xfer(self, data):

        #mask the value to a byte format for transmision
        data = (int(data) & 0xff)

        #toggle chip select and SPI transfer
        gpio.output(self.chipSelect, gpio.LOW)
        response = spi.xfer2([data])
        gpio.output(self.chipSelect, gpio.HIGH)        

        return response[0]

    ''' set a parameter of the motor driver '''
    def setParam(self, param, value):
        self.xfer(LReg.SET_PARAM | param[0])
        return self.paramHandler(param, value)

    ''' get a parameter from the motor driver '''
    def getParam(self, param):
        self.xfer(LReg.GET_PARAM | param[0])
        return self.paramHandler(param, 0)

    ''' convert twos compliment '''
    def convert(self, val):
        if val > 0x400000/2:
            val = val - 0x400000
        return val

    ''' switch case to handle parameters '''
    def paramHandler(self, param, value):
        return self.param(value, param[1])
	
	
	
	
