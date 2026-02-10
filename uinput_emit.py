#! /usr/bin/python3
#
# Requires:
#  sudo apt install python3-uinput
#
# Alternatives: 
#   - xdotool: works with X11
#   - ytype: works with Wayland
#   - ydotool: works partially with XWayland (Page_Down/Up doesn't work)
#       -> Cannot find a robust solution, that works on all desktop servers.
#

import uinput
import time, sys

# create device with declared capabilities
device = uinput.Device(list(uinput._CHAR_MAP.values()) + [
    uinput.KEY_LEFTSHIFT,
    uinput.KEY_LEFTCTRL,
    uinput.KEY_LEFTALT,

    uinput.KEY_DELETE,
    uinput.KEY_ESC,
    uinput.KEY_PAGEDOWN,
    uinput.KEY_PAGEUP,
    uinput.KEY_HOME,
    uinput.KEY_END,
    uinput.KEY_F5,
    uinput.KEY_ENTER
])

_NAME_MAP = { 
    'SHIFT': uinput.KEY_LEFTSHIFT, 
    'CTRL':  uinput.KEY_LEFTCTRL, 
    'ALT':   uinput.KEY_LEFTALT, 

    'DELETE':   uinput.KEY_DELETE, 
    'DEL':      uinput.KEY_DELETE, 
    'ESC':      uinput.KEY_ESC,
    'PAGEDOWN': uinput.KEY_PAGEDOWN,
    'PGDN':     uinput.KEY_PAGEDOWN,
    'PAGEUP':   uinput.KEY_PAGEUP,
    'PGUP':     uinput.KEY_PAGEUP,
    'HOME':     uinput.KEY_HOME,
    'END':      uinput.KEY_END,
    'F5':       uinput.KEY_F5,
    'ENTER':    uinput.KEY_ENTER,
    'RETURN':   uinput.KEY_ENTER,
}


def key_by_name(name):
    if name in _NAME_MAP:
        return _NAME_MAP[name]
    name = name.lower()
    if name in uinput._CHAR_MAP:
        return uinput._CHAR_MAP[name]

    print(f"ERROR: key name unknown: {name}")
    sys.exit(1)


## Single key example:
# device.emit_click(uinput.KEY_PAGEUP)      # emit_click() does press and release.

## Chords example CTRL-F5
# device.emit(uinput.KEY_CTRL, 1)   # press
# device.emit(uinput.KEY_F5, 1)     # press
# device.emit(uinput.KEY_F5, 0)     # release
# device.emit(uinput.KEY_CTRL, 0)   # release
# device.syn()

for arg in sys.argv[1:]:
    time.sleep(0.1)
    chord = arg.upper().split('-')
    if len(chord) == 1:
        device.emit_click(key_by_name(chord[0]))    # emit_click() does press and release.
    elif len(chord) > 1:
        key_list = []
        for k in chord:
            key_list.append(key_by_name(k))   # see if we can lookup all. exit early if not.
        # print(key_list)
        for k in key_list:
           device.emit(k, 1)           # press
        for k in reversed(key_list):
           device.emit(k, 0)           # release
    device.syn()
 
