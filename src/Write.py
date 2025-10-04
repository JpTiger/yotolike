#!/usr/bin/env python

#code adapted from project by jmcrory - more information at https://www.instructables.com/The-Pi-Must-Go-On-Pi-powered-RFID-Musical-Box/

import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522

reader = SimpleMFRC522()

try:
	text = input('New data (letters only, no spaces):')
	print("Now place your tag to write")
	reader.write(text)
	print("Written")
finally:
	GPIO.cleanup()
