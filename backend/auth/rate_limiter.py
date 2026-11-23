"""
Rate Limiting & Abuse Prevention for Maharashtra Policy Simulator Authentication (Stage 3).
Provides:
- In-memory sliding window rate limiter for IP and action keys
- Token resend cooldown enforcement
- Thread-safe tracking with zero external service dependencies
- Sanitized security logging (never logs tokens, passwords, or emails)
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

logger = logging.getLogger("backend.auth.rate_limiter")


class RateLimiter:
    """
    Thread-safe, sliding-window rate limiter for sensitive authentication endpoints.
    Tracks timestamps per key without requiring Redis or external daemons.
    Includes bounded key capacity and periodic memory cleanup.
    """

    def __init__(self, max_keys: int = 10000, cleanup_interval_seconds: float = 60.0) -> None:
        if isinstance(max_keys, bool) or not isinstance(max_keys, int) or max_keys <= 0:
            raise ValueError("max_keys must be a positive integer")

        if isinstance(cleanup_interval_seconds, bool) or not isinstance(cleanup_interval_seconds, (int, float)):
            raise ValueError("cleanup_interval_seconds must be a positive finite number")

        try:
            interval_float = float(cleanup_interval_seconds)
        except (OverflowError, TypeError, ValueError):
            raise ValueError("cleanup_interval_seconds must be a positive finite number")

        if not math.isfinite(interval_float) or interval_float <= 0:
            raise ValueError("cleanup_interval_seconds must be a positive finite number")

        self._lock = threading.Lock()
        self._history: Dict[str, deque[float]] = {}
        self._key_windows: Dict[str, int] = {}
        self._max_keys = max_keys
        self._cleanup_interval = interval_float
        self._last_cleanup = time.time()
        self._last_saturation_log: float = 0.0
        self._saturation_log_interval: float = 10.0

    def _cleanup_expired(self, now: float) -> int:
        """
        Removes keys whose timestamps have all expired beyond their registered windows.
        Must be called while holding self._lock.
        """
        keys_to_remove = []
        for key, timestamps in self._history.items():
            window = self._key_windows[key]
            cutoff = now - window
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if not timestamps:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._history[key]
            del self._key_windows[key]

        self._last_cleanup = now
        return len(keys_to_remove)

    def is_rate_limited(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """
        Checks whether 'key' has exceeded 'max_requests' within 'window_seconds'.
        If not exceeded, records the current request timestamp and returns False.
        If exceeded, returns True (request is blocked).
        Enforces a strict per-key window invariant and fails closed at key capacity.
        """
        if isinstance(max_requests, bool) or not isinstance(max_requests, int) or max_requests <= 0:
            raise ValueError("max_requests must be a positive integer")
        if isinstance(window_seconds, bool) or not isinstance(window_seconds, int) or window_seconds <= 0:
            raise ValueError("window_seconds must be a positive integer")

        now = time.time()
        cutoff = now - window_seconds

        with self._lock:
            # Periodic opportunistic global cleanup
            if now - self._last_cleanup >= self._cleanup_interval:
                self._cleanup_expired(now)

            if key in self._key_windows:
                if self._key_windows[key] != window_seconds:
                    raise ValueError(
                        f"Inconsistent window_seconds for active key: expected {self._key_windows[key]}, got {window_seconds}"
                    )
            else:
                # New key registration check against max_keys capacity
                if len(self._history) >= self._max_keys:
                    self._cleanup_expired(now)
                    if len(self._history) >= self._max_keys:
                        if now - self._last_saturation_log >= self._saturation_log_interval:
                            logger.warning(
                                "Rate limiter capacity saturated (%d active keys). Rejecting untracked requests.",
                                len(self._history),
                            )
                            self._last_saturation_log = now
                        return True

                self._history[key] = deque()
                self._key_windows[key] = window_seconds

            timestamps = self._history[key]
            # Prune timestamps outside the active sliding window
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()

            if len(timestamps) >= max_requests:
                logger.warning("Rate limit exceeded (limit: %d/%ds)", max_requests, window_seconds)
                return True

            timestamps.append(now)
            return False

    def check_resend_cooldown(
        self,
        last_created_at: Optional[datetime],
        cooldown_seconds: int = 60,
    ) -> Tuple[bool, int]:
        """
        Enforces a database-backed cooldown window between verification email requests.
        Returns:
            (is_blocked: bool, seconds_remaining: int)
        """
        if last_created_at is None:
            return False, 0

        now_utc = datetime.now(timezone.utc)
        if last_created_at.tzinfo is None:
            last_created_at = last_created_at.replace(tzinfo=timezone.utc)

        elapsed = (now_utc - last_created_at).total_seconds()
        if elapsed < cooldown_seconds:
            remaining = int(cooldown_seconds - elapsed) + 1
            return True, remaining

        return False, 0

    def cleanup(self, now: Optional[float] = None) -> int:
        """
        Explicitly runs a cleanup pass to purge expired entries.
        Supports deterministic testing with custom `now` timestamps (including 0.0).
        """
        current_time = time.time() if now is None else now
        with self._lock:
            return self._cleanup_expired(current_time)

    def reset(self) -> None:
        """Clears all in-memory rate limiting history (for isolated test runs)."""
        with self._lock:
            self._history.clear()
            self._key_windows.clear()
            self._last_cleanup = time.time()
            self._last_saturation_log = 0.0


# Global singleton instance for application authentication routes
rate_limiter = RateLimiter()
