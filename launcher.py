from __future__ import annotations

import argparse
import fcntl
import json
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
import uvicorn

from backend.app.main import app
from backend.app.lifecycle import sessions
from backend.app.settings import app_data_directory

HOST = "127.0.0.1"
PREFERRED_PORT = 8765


def wait_for_port(host: str, port: int, timeout_seconds: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://{host}:{port}/api/health", timeout=1) as response:
                if json.load(response).get("app") == "Internal CX Dashboard":
                    return True
        except (OSError, ValueError):
            pass
        time.sleep(.15)
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-browser", action="store_true", help="Headless release verification")
    parser.add_argument("--port", type=int, default=PREFERRED_PORT)
    parser.add_argument("--idle-grace", type=float, default=8)
    args = parser.parse_args()
    data_dir = app_data_directory()
    data_dir.mkdir(parents=True, exist_ok=True)
                                                                                  
    lock = (data_dir / "server.lock").open("a+")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.seek(0)
        try:
            port = int(lock.read().strip())
            if wait_for_port(HOST, port, 5) and not args.no_browser:
                webbrowser.open(f"http://{HOST}:{port}/?launch={time.time_ns()}", new=2)
        except ValueError:
            pass
        lock.close()
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((HOST, args.port))
    except OSError:
        sock.bind((HOST, 0))
    sock.listen(128)
    port = sock.getsockname()[1]
    lock.seek(0)
    lock.truncate()
    lock.write(str(port))
    lock.flush()
    sessions.start(grace=max(args.idle_grace, .1))
    server = uvicorn.Server(uvicorn.Config(app, host=HOST, port=port, log_level="warning", ws_ping_interval=10, ws_ping_timeout=20, timeout_graceful_shutdown=5))
    worker = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    worker.start()

    def open_dashboard() -> None:
        sessions.reopening()
        if wait_for_port(HOST, port):
                                                                              
                                                                             
            webbrowser.open(f"http://{HOST}:{port}/?launch={time.time_ns()}", new=2)

    try:
        if sys.platform == "darwin" and not args.no_browser:
            from AppKit import NSApplication, NSMenu, NSMenuItem, NSApplicationActivationPolicyRegular
            from Foundation import NSObject, NSTimer

            class AppDelegate(NSObject):
                def applicationShouldHandleReopen_hasVisibleWindows_(self, application, flag):
                    threading.Thread(target=open_dashboard, daemon=True).start()
                    return False

                def applicationWillTerminate_(self, notification):
                    server.should_exit = True

                def checkServer_(self, timer):
                    if sessions.expired():
                        server.should_exit = True
                    if not worker.is_alive():
                        NSApplication.sharedApplication().terminate_(None)

            native = NSApplication.sharedApplication()
            native.setActivationPolicy_(NSApplicationActivationPolicyRegular)
            delegate = AppDelegate.alloc().init()
            native.setDelegate_(delegate)
            menu = NSMenu.alloc().init()
            item = NSMenuItem.alloc().init()
            submenu = NSMenu.alloc().initWithTitle_("Internal CX Dashboard")
            submenu.addItemWithTitle_action_keyEquivalent_("Quit Internal CX Dashboard", "terminate:", "q")
            item.setSubmenu_(submenu)
            menu.addItem_(item)
            native.setMainMenu_(menu)
            timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(.25, delegate, "checkServer:", None, True)
            threading.Thread(target=open_dashboard, daemon=True).start()
            native.run()
            timer.invalidate()
        else:
            if not args.no_browser:
                threading.Thread(target=open_dashboard, daemon=True).start()
            while worker.is_alive():
                if sessions.expired():
                    server.should_exit = True
                worker.join(.25)
    finally:
        server.should_exit = True
        worker.join(6)
        sock.close()
        lock.close()


if __name__ == "__main__":
    main()
