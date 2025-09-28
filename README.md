# "Yotolike" Music Box
A homemade audio player for kids that uses RFID cards and a Raspberry Pi Zero W 2, similar to a Yoto Player or Yoto Mini.

This is based on [jmcrory's The Pi Must Go On project](https://www.instructables.com/The-Pi-Must-Go-On-Pi-powered-RFID-Musical-Box/) and would not be anything close to possible without his work. His version differs from mine in a few respects: it uses a full size pi instead of a pi zero, uses usb spearkers insteadd of a HAT, is always plugged in instead of battery powered, doesn't have a volume knob, and doesn't have a 3D-printed case. A few of the script functions also didn't work for me without a lot of vibe-coded modifications which I suspect is due to changes in how underlying libraries are handled since he wrote his instructions.

The basic steps to making the version described in this repo are:

1. [Gather all materials](https://github.com/JpTiger/yotolike/blob/main/hardware/BOM/bom.md)
2. Put together the HATs and the pi
3. Wire everything to the exposed GPIO pins [as shown in this diagram](https://html-preview.github.io/?url=https://github.com/JpTiger/yotolike/blob/main/hardware/yotolike_gpio_diagram.html)
4. Install raspbian with SSH enabled to a microsd and boot the pi for the first time
5. Follow the setup instruections in the scripts folder with the script to get the audio hat working, and then get read.py and write.py working, and then set read.py to run as a service. IF you get confused, revert back to the jmcrory version of the project.
6. Print the case, and [assemble everythig inside it](https://github.com/JpTiger/yotolike/blob/main/hardware/case/readme.md)
