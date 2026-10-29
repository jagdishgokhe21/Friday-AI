"""
FRIDAY action — open a web page in a new browser tab, through the OS.

The fallback for when the chrome_* tools cannot reach the extension. Those are
better — they can read and act on the page — but they depend on Chrome's native
host being up, and "open a new tab" should not fail just because it is not.
This asks the operating system to open the URL instead, which needs nothing.
"""
import platform
import subprocess
import webbrowser

from core import outcome

_SYSTEM = platform.system()


def _normalise(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return "about:blank"
    if "://" not in url and not url.startswith("about:"):
        url = "https://" + url
    return url


def open_url(parameters: dict, player=None) -> str:
    url = _normalise(parameters.get("url", ""))
    browser = (parameters.get("browser") or "Google Chrome").strip()
    if _SYSTEM == "Darwin":
        # `open -a` hands the URL to the running browser, which opens it in a
        # new tab of the front window — or starts the browser if it is closed.
        res = subprocess.run(["open", "-a", browser, url], capture_output=True, text=True)
        if res.returncode != 0:
            return outcome.failed("open_url", res.stderr.strip() or "the browser did not open",
                                  url=url, browser=browser)
    elif not webbrowser.open_new_tab(url):
        return outcome.failed("open_url", "no browser accepted the URL", url=url)
    if player:
        player.write_log(f"[open_url] {url}")
    return outcome.unverified("open_url", "the tab was requested from the OS; its contents cannot be read",
                              url=url, browser=browser)


TOOL = {
    "name": "open_url",
    "description": (
        "Open a web page (or a blank page) in a new tab of the user's browser, via the "
        "operating system. Use when the chrome_* tools report the browser is unreachable, "
        "or the user only wants a page opened, not read."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "url": {"type": "STRING", "description": "Address to open. Empty opens a blank tab."},
            "browser": {"type": "STRING", "description": "App name. Default: Google Chrome."},
        },
    },
    "handler": open_url,
}
