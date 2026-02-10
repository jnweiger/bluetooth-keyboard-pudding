#!/usr/bin/env python3
#
## prevent automatic usage of this device by wayland and allow normal users without sudo:
# vi /etc/udev/rules.d/99-ble-m3.rules
# # Stop libinput feeding events into X11 or wayland; Allow normal users to read BLE-M3 input devices
# SUBSYSTEM=="input", ATTRS{name}=="BLE-M3 Consumer Control", ENV{LIBINPUT_IGNORE_DEVICE}="1", MODE="0664", GROUP="input"
# SUBSYSTEM=="input", ATTRS{name}=="BLE-M3 Mouse",            ENV{LIBINPUT_IGNORE_DEVICE}="1", MODE="0664", GROUP="input"
# SUBSYSTEM=="input", ATTRS{name}=="BLE-M3 Mouse",            RUN+="/bin/sh -c 'echo 1 > /sys/class/input/%k/device/power/control'"
# ZZ
#  sudo udevadm control --reload-rules
#  sudo udevadm trigger
## prevent automatic usage of this device by X11
# xinput disable 14
# xinput disable 15
#
# Requires:
#  - sudo apt install python3-evdev
#  


import os, sys, re, time, select
import configparser, json
import subprocess
from evdev import InputDevice, ecodes, categorize

debug = False    # True or False

CONFIG_PATH = os.path.expanduser("~/.config/ble-m3.cfg")
DEFAULT_PREFIX = "BLE-M3"
EVENT_TIMEOUT = 0.2
MATCH_THRESHOLD = 50.0

UDEV_RULE_FILE="/etc/udev/rules.d/99-ble-m3.rules"
UDEV_RULE_TEMPLATE="""
# Stop libinput feeding events into X11 or wayland
SUBSYSTEM=="input", ATTRS{{id/vendor}}=="{vend}", ATTRS{{id/product}}=="{prod}", ENV{{LIBINPUT_IGNORE_DEVICE}}="1"
# Allow normal users to read BLE-M3 input devices
SUBSYSTEM=="input", ATTRS{{id/vendor}}=="{vend}", ATTRS{{id/product}}=="{prod}", MODE="0664", GROUP="input"
# Disable BLE auto suspend
SUBSYSTEM=="input", ATTRS{{id/vendor}}=="{vend}", ATTRS{{id/product}}=="{prod}", RUN+="/bin/sh -c 'echo 1 > /sys/class/input/%k/device/power/control'"

"""
UDEV_RELOAD_CMD="""
    echo 'options bluetooth hid_suspend=0' | sudo tee /etc/modprobe.d/bt-nosleep.conf
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    sudo usermod -a -G input $USER
    # (and log out and back in again)
"""


def load_cfg():
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH)

    for section in ("inputs", "device", "bindings", "scripts"):
        if section not in cfg:
            cfg[section] = {}

    if not "timeout"         in cfg["device"]: cfg["device"]["timeout"]         = str(EVENT_TIMEOUT)
    if not "match_threshold" in cfg["device"]: cfg["device"]["match_threshold"] = str(MATCH_THRESHOLD)

    return cfg


def save_cfg(cfg):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        cfg.write(f)


def check_readable_files(cfg):

    kbd   = cfg["inputs"].get("kbd")
    mouse = cfg["inputs"].get("mouse")

    err=""
    if (kbd   and not os.access(kbd,   os.R_OK)): err = err + f" {kbd}"
    if (mouse and not os.access(mouse, os.R_OK)): err = err + f" {mouse}"
    if not err:
        return True

    # ---- Not readable: print help ----
    print(f"\nERROR: Permission denied on{err}\n")
    print(f"Fix this by adding the following udev rules as e.g. {UDEV_RULE_FILE}\n")
    print("--------------------------------------------------")
    print(UDEV_RULE_TEMPLATE.format(vend=cfg["device"]["vendor"], prod=cfg["device"]["product"]))
    print("--------------------------------------------------\n")
    print(f"Then run: {UDEV_RELOAD_CMD}")

    return False


def cmd_list():
    cfg = load_cfg()
    print(" Type   Status    Device Name")
    print("------+---------+------------")
    for key in cfg["inputs"].keys():
        status = "absent"
        dev = cfg["inputs"][key]
        if os.path.exists(dev):
            if os.access(dev, os.R_OK):
                status = "OK"
            else:
                status = "no perm"
        print("%-5s | %-7s | %s" % (key, status, dev))
    print("")

    print(" Name   | Command ")
    print("--------+---------")
    for key in cfg["scripts"].keys():
        cmd = json.loads(cfg["scripts"][key])
        print("%7s | %s" % (key, subprocess.list2cmdline(cmd)))

    print(f"\nConfig file: {CONFIG_PATH}")


def cmd_scan(prefix):
    file="/proc/bus/input/devices"
    with open(file) as f:
        blocks = f.read().split("\n\n")

    kbd = mouse = None
    vend = prod = None

    for block in blocks:
        if f'Name="{prefix}' in block:
            for line in block.splitlines():
                if line.startswith("I: "):
                    # I: Bus=0005 Vendor=0e05 Product=0a00 Version=4002
                    m = re.search(r"Vendor=([0-9a-fA-F]+)\s+Product=([0-9a-fA-F]+)", line)
                    if m:
                        vend, prod = m.group(1), m.group(2)

                if line.startswith("H: Handlers="):
                    if "kbd" in line and "event" in line:
                        kbd = "/dev/input/event" + line.split("event")[-1].split()[0]
                    if "mouse" in line and "event" in line:
                        mouse = "/dev/input/event" + line.split("event")[-1].split()[0]

    if not kbd and not mouse:
        print(f"No matching mouse/kbd devices ({prefix} ...) found in {file}.\n    Try the powercycling the device.")
        sys.exit(1)

    cfg = load_cfg()
    cfg["device"]["name_prefix"] = prefix
    cfg["device"]["vendor"] = vend
    cfg["device"]["product"] = prod

    if kbd:
        cfg["inputs"]["kbd"] = kbd
        print("Keyboard:", kbd)
    if mouse:
        cfg["inputs"]["mouse"] = mouse
        print("Mouse:", mouse)

    save_cfg(cfg)
    print("Saved to", CONFIG_PATH)

    check_readable_files(cfg)


def open_dev(cfg):
    if not "inputs" in cfg:
        print(f"No inputs in {CONFIG_PATH}. please run the 'scan' command to initialize your device.")
        sys.exit(1)

    seen_missing = False
            
    kbd =   cfg["inputs"].get("kbd")
    mouse = cfg["inputs"].get("mouse")
    if debug: print("open_dev: ", kbd)
    while True:
        try:
            kbd_dev =   InputDevice(kbd)   if kbd   else None
        except (FileNotFoundError, PermissionError):
            if not seen_missing:
                print(f"Waiting for {kbd} to appear. Try pressing a button ...")
                seen_missing = True
            print(".", end='', flush=True)
            time.sleep(5)
        else:
            break
 
    if debug: print("open_dev: ", mouse)
    while True:
        try:
            mouse_dev = InputDevice(mouse) if mouse else None
        except (FileNotFoundError, PermissionError):
            if not seen_missing:
                print(f"Waiting for {mouse} to appear. Try pressing a button ...")
                seen_missing = True
            print(":", end='', flush=True)
            time.sleep(5)
        else:
            break
 
    if kbd_dev:
        kbd_dev.grab()
    if mouse_dev:
        mouse_dev.grab()
    return [kbd_dev, mouse_dev]
    mouse_dev = InputDevice(mouse) if mouse else None
    if kbd_dev:
        kbd_dev.grab()
    if mouse_dev:
        mouse_dev.grab()
    return [kbd_dev, mouse_dev]


def format_event(name, ev):
    if ev.type == ecodes.EV_KEY:
        k = categorize(ev)  # KeyEvent
        desc = "_".join(k.keycode) if type(k.keycode) in (type([]), type(())) else k.keycode
        return name + "=" + desc + "=" + str(k.keystate)
    elif ev.type == ecodes.EV_ABS:
        desc = ecodes.ABS[ev.code]
        return name + "=" + desc + "=" + str(ev.value)
    elif ev.type == ecodes.EV_REL:
        desc = ecodes.REL[ev.code]
        return name + "=" + desc + "=" + str(ev.value)
    return None


def event_sequence(cfg, kbd_mouse, endless=False, verbose=False):
    ev_list = []
    timeout = float(cfg["device"].get("timeout", EVENT_TIMEOUT))
    seen = False

    try:
        while True:
            r, _, _ = select.select([d for d in kbd_mouse if d], [], [], timeout)
            if not r:
                # we had a timeout. Ignore timeouts before the first event.
                if not ev_list:
                    continue
                if verbose and seen:
                    print("....")
                seen = False
                if not endless:
                    break
                continue

            seen = True
            for dev in r:
                ev = dev.read_one()
                if not ev:
                    continue
                ev_str = format_event("K" if dev.path == cfg["inputs"].get("kbd") else "M", ev)
                if not ev_str:
                    continue
                ev_list.append(ev_str)
                if verbose:
                    print(ev_str)
    except:
        pass

    return(ev_list)


def close_dev(kbd_mouse):
    for ding in kbd_mouse:
        if ding:
            ding.ungrab()


def cmd_monitor():
    cfg = load_cfg()
    km = open_dev(cfg)

    print("Monitoring... Ctrl+C to stop")

    event_sequence(cfg, km, endless=True, verbose=True)

    close_dev(km)


def ini_key_encode(seq):
    """ used in bindings """
    # = or : delimit keys
    # ; or # delimit comments
    #  , / @ - _  . and :alnum: are safe with python3-configparse
    #
    # CAUTION: keep in sync with event_match_score() below.
    key = ",".join(seq).replace("=", "/").replace(":", "@")
    return key.lower()


def cmd_delete(name):
    """ delete only bindings, we harmlessly keep the script, if any """
    cfg = load_cfg()
    cfg["bindings"] = {k: v for k, v in cfg["bindings"].items() if v != name}
    save_cfg(cfg)


def cmd_record(name, script=None):
    cfg = load_cfg()
    km = open_dev(cfg)

    script_json = ""
    if script:
        script_json = json.dumps(script)
        cfg["scripts"][name] = script_json
    else:
        if not name in cfg["scripts"]:
            print(f"WARNING: no script defined for this key. Please use 'record {name} script ...'")

    print("Waiting for key press...", script_json)

    seq = event_sequence(cfg, km)

    close_dev(km)

    if not seq: # don't record an empty sequence
        return

    cfg["bindings"][ini_key_encode(seq)] = name

    save_cfg(cfg)

    print(f"Recorded button {name}:")
    print("    Sequence:", seq)
    print("   Seq Count:", list(cfg["bindings"].values()).count(name))
    if name in cfg["scripts"]:
        print("      Script:", cfg["scripts"][name])


def length_ratio20(s1, s2):
    
    l1 = len(s1)
    l2 = len(s2)
    if l1 < l2:             # ensure, that l1 is the larger one.
        l1, l2 = l2, l1
        s1, s2 = s2, s1
    words = len(s2.split(','))
    if words > 19: words = 19    # ensure that words + ratio cannot not reach 20.
    ratio = l2/l1                # identical length counts 1.0 (never happens), half length returns 0.5 ...
    return (words + ratio)       # more matching words count always stronger than a better ratio


def event_match_score(name, s1, s2):
    """
    Match case insensitive.., sometimes ini files convert keys to lower case.
    100: exact match
    80--99: s1 is suffix match of s2 or vice versa.
    60--79: s1 is prefix match of s2 or vice versa.
    40--59: s1 is inside of s2 or vice versa.
    20--39: s1 and s2 have a common overlap.
    
    The position in the match range reflects the number of matching words and ratio of the string lengths.
    """
    score = 0.0
    s1 = s1.lower()
    s2 = s2.lower()
    if debug: print(f"debug: event_match_score({name}):\n", s1, "\n", s2)

    # CAUTION: keep in sync with ini_key_encode() above
    if s1 == s2:
        score = 100.0
    elif s1.endswith("," + s2) or s2.endswith("," + s1):
        score = 80.0 + length_ratio20(s1, s2)
    elif s1.startswith(s2 + ",") or s2.startswith(s1 + ","):
        score = 60.0 + length_ratio20(s1, s2)
    elif "," + s2 + "," in s1 or "," + s1 + "," in s2:
        score = 40.0 + length_ratio20(s1, s2)
    # FIXME: common overlap not implemented.
    if debug: print("returning score: ", score)
    return score


def cmd_run():
    cfg = load_cfg()
    min_score = float(cfg["device"]["match_threshold"])
    bindings = cfg["bindings"]
    scripts = cfg["scripts"]

    while True:
        km = open_dev(cfg)
    
        if debug: print("Running...")
    
        while True:
            try:
                seq_seen = event_sequence(cfg, km)
                if not seq_seen:
                    break
                score = {}
                seq_str = ini_key_encode(seq_seen)
                for seq_wanted, name in bindings.items():
                    s = event_match_score(name, seq_str, seq_wanted)
                    score[name] = max(s, score.get(name, 0))    # find the maximum score per name
                if debug: print("score: ", score)
    
                best_name = max(score, key=score.get)
                if score[best_name] >= min_score:
                    if debug: print("Matched:", best_name, scripts[best_name])
                    cmd = json.loads(scripts[best_name])
                    r = subprocess.run(cmd)
                    if r.returncode:
                        print("returncode: ", r.returncode)
                elif score[best_name] == 0:
                    print(f"Event sequence unknown:\n    {seq_seen}\n   Try the 'record' command to add this.\nOr manually add a binding in {CONFIG_PATH}:\n{seq_str} = NAME")
                else:
                    print(f"Low score {score[best_name]} -> {best_name} for event sequence:\n    {seq_seen}\n   Try adjustments in {CONFIG_PATH}")
    
            except OSError as e:
                if e.errno == 19:  # ENODEV - No such device
                    print("Device disappeared (BLE sleep)")
                else:
                    raise  # Re-raise other OS errors
            except FileNotFoundError as e:
                if e.errno == 2:  # ENOENT
                    print("Device node disappeared (BLE sleep)")
                else:
                    raise  # Re-raise other OS errors
    
        if debug: print(" ... Closing ...")
        try:
            close_dev(km)
        except:
            pass

        if not seq_seen:    # user probably pressed CTRL-C
            break
        time.sleep(5)


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ('help', '-h', '--help'):
        print("Usage: scan|monitor|record|list|delete|run")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "scan":
        prefix = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PREFIX
        cmd_scan(prefix)

    elif cmd == "list":
        cmd_list()

    elif cmd == "monitor":
        cmd_monitor()

    elif cmd == "record":
        if len(sys.argv) < 3:
            print("Capture an event (or event sequene) that correspond to a key press,")
            print("give it a name, and define the shell script, that this key should trigger:")
            print(f"     {sys.argv[0]} record <name> <script> ...")
            print("Capture additional key presses for the same named command:")
            print(f"     {sys.argv[0]} record <name>")
            print("")
            print("You may record multiply sequences for a name. A seq counter increments, if the sequence was new.")
            print("Try double click or recording again, after a different button was pressed.")
            sys.exit(1)
        cmd_record(sys.argv[2], sys.argv[3:])

    elif cmd == "delete":
        if len(sys.argv) < 3:
            print(f"     {sys.argv[0]} delete <name>")
            sys.exit(1)
        cmd_delete(sys.argv[2])

    elif cmd == "run":
        cmd_run()

    else:
        print("Unknown command")

if __name__ == "__main__":
    main()


