"""In-memory diagnostic tap ring buffer for observing internal state transitions."""

from __future__ import annotations

import datetime
from collections import deque
from typing import Any


class DiagnosticTapRingBuffer:
    """Bounded ring buffer recording telemetry events and state transitions."""

    def __init__(self, capacity: int = 200) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._capacity = capacity
        self._buffer: deque[dict[str, Any]] = deque(maxlen=capacity)

    @property
    def capacity(self) -> int:
        """Return maximum ring buffer capacity."""
        return self._capacity

    def record(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Append a structured diagnostic event to the ring buffer."""
        entry = {
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "event_type": event_type,
            "payload": payload,
        }
        self._buffer.append(entry)
        return entry

    def snapshot(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent diagnostic events (newest last)."""
        items = list(self._buffer)
        if limit > 0:
            return items[-limit:]
        return items

    def clear(self) -> None:
        """Clear all recorded diagnostic events."""
        self._buffer.clear()
