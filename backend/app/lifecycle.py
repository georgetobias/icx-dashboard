"""Desktop lifetime follows connected dashboard tabs; development servers opt out."""
from __future__ import annotations
import threading
import time


class BrowserSessions:
    def __init__(self) -> None:
        self.enabled = False
        self.connections: set[str] = set()
        self.deadline = float("inf")
        self.grace = 8.0
        self.lock = threading.RLock()

    def start(self, grace: float = 8.0, startup_timeout: float = 120.0) -> None:
        with self.lock:
            self.enabled = True
            self.connections.clear()
            self.grace = grace
            self.deadline = time.monotonic() + startup_timeout

    def connect(self, session: str) -> None:
        with self.lock:
            self.connections.add(session)
            self.deadline = float("inf")

    def disconnect(self, session: str) -> None:
        with self.lock:
            self.connections.discard(session)
            if not self.connections:
                self.deadline = time.monotonic() + self.grace

    def reopening(self) -> None:
        with self.lock:
            self.deadline = time.monotonic() + 120

    def expired(self) -> bool:
        with self.lock:
            return self.enabled and not self.connections and time.monotonic() >= self.deadline


sessions = BrowserSessions()
