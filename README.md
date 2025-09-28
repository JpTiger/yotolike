# "Yotolike" Music Box
A homemade audio player for kids that uses RFID cards and a Raspberry Pi Zero W 2, similar to a Yoto Player or Yoto Mini.

This is based on [jmcrory's The Pi Must Go On project](https://www.instructables.com/The-Pi-Must-Go-On-Pi-powered-RFID-Musical-Box/) and would not be anything close to possible without his work. His version differs from mine in a few respects: it uses a full size pi instead of a pi zero, uses usb spearkers insteadd of a HAT, is always plugged in instead of battery powered, doesn't have a volume knob, and doesn't have a 3D-printed case. A few of the script functions also didn't work for me without a lot of vibe-coded modifications which I suspect is due to changes in how underlying libraries are handled since he wrote his instructions.

The basic steps to making the version described in this repo are:

1. [Gather all materials](https://github.com/JpTiger/yotolike/blob/main/hardware/BOM/bom.md)
2. Put together the HATs and the pi
3. Wire everything to the exposed GPIO pins [as shown in this diagram](https://html-preview.github.io/?url=https://github.com/JpTiger/yotolike/blob/main/hardware/yotolike_gpio_diagram.html). This involved some soldering in my case to get the pins onto the RFID reader and to make the momentary button work jumper cables
4. Install Bookwork Raspbian lite via Raspbian imager with SSH enabled and wifi details included to a microsd and boot the pi for the first time
5. SSH in and update everything in Raspbian
6. use raspi-config to activate i2c, spi, and serial interfaces
7. edit /boot/firmware/config.txt to add/uncomment a couple lines to get the sound card working:
  - `dtparam=i2c_arm=on dtparam=audio=off`
  - `dtoverlay=wm8960-soundcard`
  - test speakers. Figuring this out took me a truly stupid amount of time so I hope it's as simple as following the above for you.
8. install python 3
  - `sudo apt-get install python3-dev python3-pip`
9. make a project directory (in my case /home/joel/musicbox)
10. use pip to install spidev and mfrc522
11. make write.py (standard version in [the jmcrory tutorial](https://www.instructables.com/The-Pi-Must-Go-On-Pi-powered-RFID-Musical-Box/))
12. use write.py to write to a card or two
13. copy over [Read.py](https://github.com/JpTiger/yotolike/blob/main/src/Read.py)
14. use [the power button setup script](https://github.com/JpTiger/yotolike/blob/main/scripts/momentary_pi_button_setup.sh)
15. create the musicbox systemd service and make it run on boot
  - `sudo systemctl daemon-reload`
  - `sudo systemctl enable musicbox.service`
  - `sudo systemctl start musicbox.service`
16. reboot, test one of the cards you wrote to see if it's all working
17. print the case, and [assemble everythig inside it](https://github.com/JpTiger/yotolike/blob/main/hardware/case/readme.md)
