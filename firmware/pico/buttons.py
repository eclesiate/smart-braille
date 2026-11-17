"""Software debouncing for the four buttons. No imports."""


class Debouncer:
    """Reports one press when an active-low input has been low for hold_ms."""

    def __init__(self, hold_ms):
        self.hold_ms = hold_ms
        self._low_since = None
        self._reported = False

    def sample(self, level, now_ms):
        """level: 1 = released, 0 = pressed. Returns True once per press."""
        if level:
            self._low_since = None
            self._reported = False
            return False
        if self._low_since is None:
            self._low_since = now_ms
            return False
        if not self._reported and now_ms - self._low_since >= self.hold_ms:
            self._reported = True
            return True
        return False
