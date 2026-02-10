BLE-M3
------

Use a bluetooth remote control to start commands on a Linux desktop.
The BLE-M3 device is an inexpensive bluetooth low energy device that features a total of 6 pushbuttons.
Many similar devices are sold as
- TIKTok Bluetooth4.0-remote for IOSAndroid-App
- wireless page turner

The device connects as two HID devices, keyboard and mouse, the buttons send mixtures of mouse movements 
and key presses. 

The buttons on my device are: Left, Right, Up, Down, OK, Camera.

This is probably special tailored for one particular user interface layout, so that the buttons 
on the remote correspond to those on the app.

On Linux, these special mouse and keyboard events result in nothing useful.

This tool ble-m3.py intercepts the events from the device and prevents them from direclty affecting the desktop.
Instead, we can 
- record whatever sequene of events each button send, 
- map that to shell commands
- and when properly set up, run a loop that listens for buttons and executs the corresponding commands.


I am using this during presentations, to e.g. start a video, or switch to another presentaiton.


Libreoffice Impress -> Bildschirmpräsentation -> Präsentationseinstellungen
	Fernsteuerung
	[x] Fernsteuerung aktivieren
	[x] Unsichere WLAN-Verbindungen aktivieren
Restart Libreoffice Impress.
	-> TCP port 1599 is now listening for e.g. handshake and eventually "transition_next"

printf 'LO_SERVER_CLIENT_PAIR\nshell-remote\n0000\n\n%s\n\n' transition_next | nc localhost 1599 -w 1
# kind of works
# loimpress produces huge quanitites of output on the socket.
#  -> If we don't read everything, it locks up eventually.


Try:
sudo apt install xdotool
sudo apt install ydotool
https://github.com/ReimuNotMoe/ydotool/releases

evtest

Preparations
------------
# if this exists: (it does not on my ubuntu
test -f /sys/module/bluetooth/parameters/hid_suspend && echo 0 | sudo tee /sys/module/bluetooth/parameters/hid_suspend
# Disable Bluetooth HID autosuspend at kernel/module level
echo 'options bluetooth hid_suspend=0' | sudo tee /etc/modprobe.d/bt-nosleep.conf
echo 1 | sudo tee /sys/class/input/input13/device/power/control
echo 1 | sudo tee /sys/class/input/input14/device/power/control
