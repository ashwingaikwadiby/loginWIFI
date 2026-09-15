"""Offline check of the Palo Alto login flow. Run: python3 test_autologin.py"""
import autologin as a

a.log = lambda m: None
URL = "https://firewall.iitgoa.ac.in:6082/php/uid.php?vsys=1&rule=1&token=T"
a.get_login_page = lambda: (URL, '<script>thisForm.preauthid.value = "6aa41c8c0002b34d";</script>')
sent = {}

def ok_fetch(url, data=None, timeout=10):
    sent.update(url=url, data=data)
    return "<p><b>User Authenticated</b></p>"

a.fetch = ok_fetch
assert a.do_login("dom\\user", "pw")
assert sent["url"] == URL
assert sent["data"] == {"inputStr": "", "escapeUser": "dom\\\\user", "preauthid": "6aa41c8c0002b34d",
                        "user": "dom\\user", "passwd": "pw", "ok": "Login"}

a.fetch = lambda *_, **__: 'var respMsg = "Invalid username or password";'
assert not a.do_login("user", "bad")

a.get_login_page = lambda: ("http://example.com/", "<html>some other network</html>")
assert not a.do_login("user", "pw")
print("ok")
