from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _Pending:
    payload: bytes
    sent_at: float


class SenderWindow:
    def __init__(self, window_size: int = 32, timeout: float = 1.0):
        if window_size < 1 or timeout <= 0:
            raise ValueError("invalid ARQ settings")
        self.window_size = window_size
        self.timeout = timeout
        self._pending: dict[int, _Pending] = {}

    def queue(self, sequence: int, payload: bytes, now: float = 0.0) -> None:
        if len(self._pending) >= self.window_size and sequence not in self._pending:
            raise BufferError("send window full")
        self._pending[sequence] = _Pending(bytes(payload), now)

    def acknowledge(self, sequence: int) -> None:
        self._pending.pop(sequence, None)

    def due(self, now: float) -> list[tuple[int, bytes]]:
        result = []
        for sequence, item in self._pending.items():
            if now - item.sent_at >= self.timeout:
                item.sent_at = now
                result.append((sequence, item.payload))
        return result

    @property
    def complete(self) -> bool:
        return not self._pending


class ReceiverWindow:
    def __init__(self, window_size: int = 32, start_sequence: int = 0):
        if window_size < 1:
            raise ValueError("invalid window size")
        self.window_size = window_size
        self.next_sequence = start_sequence
        self._buffer: dict[int, bytes] = {}

    def receive(self, sequence: int, payload: bytes) -> list[bytes]:
        if sequence < self.next_sequence or sequence >= self.next_sequence + self.window_size:
            return []
        self._buffer.setdefault(sequence, bytes(payload))
        ready = []
        while self.next_sequence in self._buffer:
            ready.append(self._buffer.pop(self.next_sequence))
            self.next_sequence += 1
        return ready

    def ack_state(self) -> tuple[int, tuple[int, ...]]:
        return self.next_sequence - 1, tuple(sorted(self._buffer))
