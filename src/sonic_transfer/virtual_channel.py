from __future__ import annotations

import random


class VirtualChannel:
    def __init__(self, loss_rate: float = 0.0, noise: float = 0.0, frequency_offset: float = 0.0, seed: int | None = None):
        if not 0 <= loss_rate < 1 or noise < 0:
            raise ValueError("invalid channel settings")
        self.loss_rate, self.noise, self.frequency_offset = loss_rate, noise, frequency_offset
        self.random = random.Random(seed)

    def transmit(self, samples: list[float]) -> list[float]:
        if self.random.random() < self.loss_rate:
            return []
        return [sample + self.random.gauss(0.0, self.noise) for sample in samples]
