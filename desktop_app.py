"""Launch Life Manager as a native desktop window.

Starts Streamlit in the background, waits for the port to accept
connections, then opens a pywebview window pointed at it.
Closing the window terminates Streamlit.
"""
import ctypes
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import webview

FROZEN = getattr(sys, "frozen", False)
if FROZEN:
    PROJECT_ROOT = Path(sys.executable).resolve().parent.parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent

PORT = 8501
URL = f"http://localhost:{PORT}"
ICON = PROJECT_ROOT / "config" / "lifemanager.ico"
APP_ID = "LifeManager.Desktop.1"


def find_pythonw() -> str:
    if not FROZEN:
        return sys.executable
    candidate = shutil.which("pythonw") or shutil.which("python")
    return candidate or "pythonw"


def set_app_user_model_id() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass


def _find_window(title: str, timeout: float = 5.0) -> int:
    user32 = ctypes.windll.user32
    deadline = time.time() + timeout
    while time.time() < deadline:
        hwnd = user32.FindWindowW(None, title)
        if hwnd:
            return hwnd
        time.sleep(0.1)
    return 0


def apply_window_icon(title: str = "Life Manager") -> None:
    """Force the taskbar / titlebar icon after the window is shown."""
    if sys.platform != "win32" or not ICON.exists():
        return
    try:
        user32 = ctypes.windll.user32
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010
        LR_DEFAULTSIZE = 0x00000040
        WM_SETICON = 0x0080
        ICON_SMALL, ICON_BIG = 0, 1

        hwnd = _find_window(title)
        if not hwnd:
            return

        for size, which in ((16, ICON_SMALL), (32, ICON_BIG)):
            h_icon = user32.LoadImageW(
                None, str(ICON), IMAGE_ICON, size, size,
                LR_LOADFROMFILE | LR_DEFAULTSIZE,
            )
            if h_icon:
                user32.SendMessageW(hwnd, WM_SETICON, which, h_icon)
    except Exception:
        pass


def bring_to_front(title: str = "Life Manager") -> None:
    """Force the window to the foreground on launch."""
    if sys.platform != "win32":
        return
    try:
        user32 = ctypes.windll.user32
        SW_RESTORE = 9
        SW_SHOW = 5
        HWND_TOPMOST = -1
        HWND_NOTOPMOST = -2
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_SHOWWINDOW = 0x0040

        hwnd = _find_window(title)
        if not hwnd:
            return

        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.ShowWindow(hwnd, SW_SHOW)
        # Topmost pulse: bypasses foreground lock, then release
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
        user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
        user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_for_server(timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_open(PORT):
            return True
        time.sleep(0.25)
    return False


def start_streamlit() -> subprocess.Popen:
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    return subprocess.Popen(
        [
            find_pythonw(),
            "-m",
            "streamlit",
            "run",
            str(PROJECT_ROOT / "app.py"),
            "--server.port",
            str(PORT),
            "--server.headless",
            "true",
            "--server.enableStaticServing",
            "true",
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )


def main() -> None:
    set_app_user_model_id()
    proc = start_streamlit()
    try:
        if not wait_for_server():
            return
        window = webview.create_window(
            "Life Manager",
            URL,
            width=1440,
            height=900,
            min_size=(1024, 700),
        )
        def _on_shown() -> None:
            apply_window_icon()
            bring_to_front()

        window.events.shown += _on_shown
        webview.start(icon=str(ICON) if ICON.exists() else None)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
