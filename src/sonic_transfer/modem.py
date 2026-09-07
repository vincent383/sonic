from __future__ import annotations

import math
import struct
import zlib
from dataclasses import dataclass


class DecodeError(ValueError):
    pass


@dataclass(frozen=True)
class ModemConfig:
    sample_rate: int = 48_000
    mode: str = "fast"

    @property
    def symbol_samples(self) -> int:
        return 128 if self.mode == "fast" else 192

    @property
    def carriers(self) -> int:
        return 8 if self.mode == "fast" else 6


class Modem:
    _MAGIC = b"SMD1"

    def __init__(self, config: ModemConfig = ModemConfig()):
        if config.sample_rate < 4000 or config.mode not in {"fast", "robust"}:
            raise ValueError("invalid modem configuration")
        self.config = config

    def encode(self, data: bytes) -> list[float]:
        packet = self._MAGIC + struct.pack("!I", len(data)) + data + struct.pack("!I", zlib.crc32(data) & 0xFFFFFFFF)
        bits = [(byte >> shift) & 1 for byte in packet for shift in range(7, -1, -1)]
        n, count = self.config.symbol_samples, self.config.carriers
        bits.extend([0] * ((count * 2 - len(bits) % (count * 2)) % (count * 2)))
        # A repeated alternating pilot gives a receiver an unambiguous block boundary.
        samples = [0.0] * (n * 2)
        for symbol in range(0, len(bits), count * 2):
            values = bits[symbol:symbol + count * 2]
            for i in range(n):
                value = 0.0
                t = i / self.config.sample_rate
                for carrier in range(count):
                    pair = values[carrier * 2:carrier * 2 + 2]
                    phase = (pair[0] * 2 + pair[1]) * math.pi / 2
                    value += math.cos(2 * math.pi * (500 + carrier * self.config.sample_rate / n) * t + phase)
                samples.append(value / count)
        return samples

    def decode(self, samples: list[float]) -> bytes:
        n, count = self.config.symbol_samples, self.config.carriers
        if len(samples) < n * 2 or (len(samples) - n * 2) % n:
            raise DecodeError("incomplete modem symbols")
        bits: list[int] = []
        for offset in range(n * 2, len(samples), n):
            block = samples[offset:offset + n]
            for carrier in range(count):
                frequency = 500 + carrier * self.config.sample_rate / n
                cos_sum = sin_sum = 0.0
                for i, sample in enumerate(block):
                    angle = 2 * math.pi * frequency * i / self.config.sample_rate
                    cos_sum += sample * math.cos(angle)
                    sin_sum += sample * math.sin(angle)
                phase = math.atan2(-sin_sum, cos_sum) % (2 * math.pi)
                symbol = int(round(phase / (math.pi / 2))) % 4
                bits.extend((symbol >> 1, symbol & 1))
        raw = bytearray()
        for offset in range(0, len(bits) - 7, 8):
            value = 0
            for bit in bits[offset:offset + 8]:
                value = (value << 1) | bit
            raw.append(value)
        if len(raw) < 12 or bytes(raw[:4]) != self._MAGIC:
            raise DecodeError("modem preamble or header mismatch")
        length = struct.unpack("!I", raw[4:8])[0]
        end = 8 + length + 4
        if end > len(raw):
            raise DecodeError("truncated modem packet")
        data = bytes(raw[8:8 + length])
        expected = struct.unpack("!I", raw[8 + length:end])[0]
        if zlib.crc32(data) & 0xFFFFFFFF != expected:
            raise DecodeError("modem CRC mismatch")
        return data
