#!/usr/bin/env python3
"""IIT Goa WiFi auto-login — keeps you authenticated on the campus Fortinet portal."""

import sys, os, time, re, ssl, subprocess, platform, signal, getpass
from urllib.request import Request, build_opener, HTTPSHandler
from urllib.parse import urlencode
from pathlib import Path
from datetime import datetime

DIR = Path(__file__).resolve().parent
ENV_FILE = DIR / ".env"
LOG_FILE = DIR / "autologin.log"
PID_FILE = DIR / ".pid"

PORTAL = "https://firewall.iitgoa.ac.in:1003"
CHECK_URL = "http://connectivitycheck.gstatic.com/generate_204"
INTERVAL = 5

# Firewall uses self-signed cert
_ssl = ssl.create_default_context()
_ssl.check_hostname = False
_ssl.verify_mode = ssl.CERT_NONE
_opener = build_opener(HTTPSHandler(context=_ssl))

SYSTEM = platform.system()


# ── Helpers ──

def load_creds():
    if not ENV_FILE.exists():
        print(f"No .env found. Run: python {sys.argv[0]} setup")
        sys.exit(1)
    creds = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            creds[k.strip()] = v.strip()
    return creds.get("WIFI_USERNAME", ""), creds.get("WIFI_PASSWORD", "")


def log(msg):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
        if LOG_FILE.stat().st_size > 100_000:
            lines = LOG_FILE.read_text().splitlines()
            LOG_FILE.write_text("\n".join(lines[-200:]) + "\n")
    except Exception:
        pass


def fetch(url, data=None, timeout=10):
    try:
        body = urlencode(data).encode() if data else None
        with _opener.open(Request(url, data=body), timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def is_online():
    try:
        # generate_204 returns HTTP 204 when online; portal intercepts with != 204
        r = _opener.open(CHECK_URL, timeout=5)
        return r.status == 204
    except Exception:
        return False


def get_login_page():
    page = fetch(f"{PORTAL}/login?")
    if page and "magic" in page:
        return page
    # When unauthenticated, firewall intercepts HTTP and redirects to /fgtauth?...
    try:
        with _opener.open(CHECK_URL, timeout=10) as r:
            if "firewall" in r.url:
                log(f"Following redirect: {r.url}")
                return fetch(r.url)
    except Exception:
        pass
    return None


def do_login(username, password):
    page = get_login_page()
    if not page:
        log("FAIL: couldn't reach portal")
        return False

    m = re.search(r'name="magic" value="([^"]+)"', page)
    if not m:
        log("FAIL: no magic token (already logged in?)")
        return False

    redir = re.search(r'name="4Tredir" value="([^"]+)"', page)
    redir = redir.group(1) if redir else f"{PORTAL}/login?"

    resp = fetch(f"{PORTAL}/", data={
        "4Tredir": redir,
        "magic": m.group(1),
        "username": username,
        "password": password,
    })

    if resp and "keepalive" in resp.lower():
        log("OK: logged in")
        return True
    log("FAIL: login rejected")
    return False


def _pid_alive(pid):
    try:
        if SYSTEM == "Windows":
            r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"],
                               capture_output=True, text=True)
            return str(pid) in r.stdout
        else:
            os.kill(pid, 0)
            return True
    except (OSError, ProcessLookupError):
        return False


# ── Service install/uninstall ──

def install_service():
    py = sys.executable
    script = Path(__file__).resolve()

    if SYSTEM == "Linux":
        d = Path.home() / ".config/systemd/user"
        d.mkdir(parents=True, exist_ok=True)
        (d / "wifi-autologin.service").write_text(
            "[Unit]\n"
            "Description=IIT Goa WiFi auto-login\n"
            "After=network-online.target\nWants=network-online.target\n\n"
            "[Service]\nType=simple\n"
            f"ExecStart={py} {script} run\n"
            "Restart=always\nRestartSec=10\n\n"
            "[Install]\nWantedBy=default.target\n")
        subprocess.run(["systemctl", "--user", "daemon-reload"])
        subprocess.run(["systemctl", "--user", "enable", "wifi-autologin.service"])
        subprocess.run(["systemctl", "--user", "start", "wifi-autologin.service"])
        try:
            subprocess.run(["loginctl", "enable-linger", os.getlogin()],
                           stderr=subprocess.DEVNULL)
        except Exception:
            pass
        print("Installed as systemd user service (starts on boot).")

    elif SYSTEM == "Darwin":
        d = Path.home() / "Library/LaunchAgents"
        d.mkdir(parents=True, exist_ok=True)
        (d / "com.iitgoa.wifi-autologin.plist").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0"><dict>\n'
            '  <key>Label</key><string>com.iitgoa.wifi-autologin</string>\n'
            '  <key>ProgramArguments</key><array>\n'
            f'    <string>{py}</string><string>{script}</string><string>run</string>\n'
            '  </array>\n'
            '  <key>RunAtLoad</key><true/>\n'
            '  <key>KeepAlive</key><true/>\n'
            f'  <key>StandardOutPath</key><string>{LOG_FILE}</string>\n'
            f'  <key>StandardErrorPath</key><string>{LOG_FILE}</string>\n'
            '</dict></plist>')
        subprocess.run(["launchctl", "load",
                        str(d / "com.iitgoa.wifi-autologin.plist")])
        print("Installed as LaunchAgent (starts on login).")

    elif SYSTEM == "Windows":
        startup = Path(os.environ.get("APPDATA", "")) / \
            r"Microsoft\Windows\Start Menu\Programs\Startup"
        pythonw = Path(py).parent / "pythonw.exe"
        if not pythonw.exists():
            pythonw = py
        (startup / "wifi-autologin.bat").write_text(
            f'@echo off\nstart "" "{pythonw}" "{script}" run\n')
        print("Installed to Windows Startup folder (starts on login).")
        cmd_start()


def uninstall_service():
    if SYSTEM == "Linux":
        subprocess.run(["systemctl", "--user", "stop", "wifi-autologin.service"],
                       capture_output=True)
        subprocess.run(["systemctl", "--user", "disable", "wifi-autologin.service"],
                       capture_output=True)
        unit = Path.home() / ".config/systemd/user/wifi-autologin.service"
        unit.unlink(missing_ok=True)
        subprocess.run(["systemctl", "--user", "daemon-reload"])
    elif SYSTEM == "Darwin":
        p = Path.home() / "Library/LaunchAgents/com.iitgoa.wifi-autologin.plist"
        subprocess.run(["launchctl", "unload", str(p)], capture_output=True)
        p.unlink(missing_ok=True)
    elif SYSTEM == "Windows":
        startup = Path(os.environ.get("APPDATA", "")) / \
            r"Microsoft\Windows\Start Menu\Programs\Startup"
        (startup / "wifi-autologin.bat").unlink(missing_ok=True)
        cmd_stop()
    print("Autostart removed.")


# ── Commands ──

def cmd_setup():
    print("IIT Goa WiFi Auto-Login Setup")
    print("=" * 35)

    old_u, old_p = ("", "")
    if ENV_FILE.exists():
        old_u, old_p = load_creds()

    u = input(f"Username [{old_u or 'roll number'}]: ").strip() or old_u
    p = getpass.getpass(f"Password [{'****' if old_p else ''}]: ").strip() or old_p
    if not u or not p:
        print("Both fields required.")
        sys.exit(1)

    ENV_FILE.write_text(f"WIFI_USERNAME={u}\nWIFI_PASSWORD={p}\n")
    if SYSTEM != "Windows":
        os.chmod(ENV_FILE, 0o600)
    print(f"Saved to {ENV_FILE}")

    a = input("Install autostart (runs on boot)? [Y/n]: ").strip().lower()
    if a in ("", "y", "yes"):
        install_service()


def cmd_run():
    username, password = load_creds()
    log(f"Started — checking every {INTERVAL}s")
    PID_FILE.write_text(str(os.getpid()))
    try:
        while True:
            if not is_online():
                log("Offline — attempting login...")
                if not do_login(username, password):
                    time.sleep(5)
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        log("Stopped.")
    finally:
        PID_FILE.unlink(missing_ok=True)


def cmd_login():
    username, password = load_creds()
    print("Testing login...")
    if do_login(username, password):
        print("Success!")
    else:
        print("Failed — check credentials in .env")


def cmd_status():
    if SYSTEM == "Linux":
        subprocess.run(["systemctl", "--user", "status",
                        "wifi-autologin.service", "--no-pager"])
    elif SYSTEM == "Darwin":
        r = subprocess.run(["launchctl", "list", "com.iitgoa.wifi-autologin"],
                           capture_output=True)
        print("Running" if r.returncode == 0 else "Not running")
    else:
        if PID_FILE.exists():
            pid = int(PID_FILE.read_text().strip())
            print(f"Running (PID {pid})" if _pid_alive(pid) else "Not running")
        else:
            print("Not running")


def cmd_start():
    if SYSTEM == "Linux":
        subprocess.run(["systemctl", "--user", "start", "wifi-autologin.service"])
    elif SYSTEM == "Darwin":
        p = Path.home() / "Library/LaunchAgents/com.iitgoa.wifi-autologin.plist"
        subprocess.run(["launchctl", "load", str(p)])
    else:
        script = Path(__file__).resolve()
        subprocess.Popen(
            [sys.executable, str(script), "run"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=0x08000000 if SYSTEM == "Windows" else 0,
            start_new_session=(SYSTEM != "Windows"),
        )
    print("Started.")


def cmd_stop():
    if SYSTEM == "Linux":
        subprocess.run(["systemctl", "--user", "stop", "wifi-autologin.service"])
    elif SYSTEM == "Darwin":
        p = Path.home() / "Library/LaunchAgents/com.iitgoa.wifi-autologin.plist"
        subprocess.run(["launchctl", "unload", str(p)])
    else:
        if PID_FILE.exists():
            pid = int(PID_FILE.read_text().strip())
            try:
                if SYSTEM == "Windows":
                    subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                                   capture_output=True)
                else:
                    os.kill(pid, signal.SIGTERM)
            except Exception:
                pass
            PID_FILE.unlink(missing_ok=True)
    print("Stopped.")


def cmd_restart():
    cmd_stop()
    time.sleep(1)
    cmd_start()


def cmd_log():
    if not LOG_FILE.exists():
        print("No log yet.")
        return
    lines = LOG_FILE.read_text().splitlines()
    follow = len(sys.argv) > 2 and sys.argv[2] == "-f"
    if not follow:
        for l in lines[-20:]:
            print(l)
        return
    with open(LOG_FILE) as f:
        f.seek(0, 2)
        try:
            while True:
                l = f.readline()
                if l:
                    print(l, end="", flush=True)
                else:
                    time.sleep(0.5)
        except KeyboardInterrupt:
            pass


def cmd_uninstall():
    uninstall_service()


COMMANDS = {
    "setup": cmd_setup, "run": cmd_run, "login": cmd_login,
    "status": cmd_status, "start": cmd_start, "stop": cmd_stop,
    "restart": cmd_restart, "log": cmd_log, "uninstall": cmd_uninstall,
}

HELP = """Usage: python autologin.py <command>

Commands:
  setup      Save credentials + install autostart
  status     Check if running
  start      Start the service
  stop       Stop the service
  restart    Restart the service
  log        Show last 20 lines (add -f to follow live)
  login      Test a single login attempt
  uninstall  Remove autostart"""

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd in ("-h", "--help", "help"):
        print(HELP)
        sys.exit(0)
    if cmd not in COMMANDS:
        print(f"Unknown: {cmd}\n{HELP}")
        sys.exit(1)
    COMMANDS[cmd]()
