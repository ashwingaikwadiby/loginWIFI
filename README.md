# loginWIFI

Auto-login to IIT Goa campus WiFi. Runs in background, detects when internet drops, re-authenticates to the Fortinet captive portal within seconds. Works on Linux, macOS, and Windows.

**Python 3 only. No dependencies.**

## Setup

```bash
git clone https://github.com/ashwingaikwadiby/loginWIFI.git
cd loginWIFI
python3 autologin.py setup
```

`setup` will ask for your roll number and password, then install autostart so it runs on boot.

## Commands

```
python3 autologin.py status     # check if running
python3 autologin.py start      # start the service
python3 autologin.py stop       # stop the service
python3 autologin.py restart    # restart
python3 autologin.py log        # last 20 log lines
python3 autologin.py log -f     # follow log live
python3 autologin.py login      # test a single login
python3 autologin.py uninstall  # remove autostart
```

Linux/macOS shortcut (after setup): `wifi status`, `wifi log`, etc.

## How it works

Every 5 seconds, it pings a connectivity check URL. If it fails, it fetches the Fortinet login page, extracts the CSRF token, and POSTs your credentials. That's it.

## Uninstall

```bash
python3 autologin.py uninstall
```
