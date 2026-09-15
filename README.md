# loginWIFI

Auto-login to IIT Goa campus WiFi. Runs in background, detects when internet drops, re-authenticates to the Palo Alto captive portal within seconds. Works on Linux, macOS, and Windows.

**Python 3 only. No dependencies.**

## Setup

```bash
git clone https://github.com/ashwingaikwadiby/loginWIFI.git
cd loginWIFI
python autologin.py setup
```

> **Note:** Use `python` or `python3` — whichever works on your system.

> **macOS:** don't keep the folder in Desktop, Documents or Downloads — macOS blocks background (launchd) jobs from reading those, so the service silently fails. `~/loginWIFI` is fine.

> **Updating:** after `git pull`, run `python autologin.py restart`.

`setup` will ask for your roll number and password, then install autostart so it runs on boot.

## Commands

```
python autologin.py status     # check if running
python autologin.py start      # start the service
python autologin.py stop       # stop the service
python autologin.py restart    # restart
python autologin.py log        # last 20 log lines
python autologin.py log -f     # follow log live
python autologin.py login      # test a single login
python autologin.py uninstall  # remove autostart
```

Linux/macOS shortcut (after setup): `wifi status`, `wifi log`, etc.

## How it works

Every 5 seconds, it pings a connectivity check URL. If the firewall redirects it to the Palo Alto login page (`firewall.iitgoa.ac.in:6082`), it grabs the session cookie and one-time `preauthid`, and POSTs your credentials. That's it.

## Uninstall

```bash
python autologin.py uninstall
```
