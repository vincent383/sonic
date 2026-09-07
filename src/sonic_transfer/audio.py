from __future__ import annotations

import struct
from queue import Empty, Queue

from .modem import Modem, ModemConfig
from .protocol import Frame, decode_frame, encode_frame


def list_devices() -> list[dict[str, object]]:
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise RuntimeError("install sounddevice to access audio devices") from exc
    return [dict(device) for device in sd.query_devices()]


class AudioDuplex:
    """Raw full-duplex PortAudio adapter; protocol sessions can use send/receive."""

    def __init__(self, input_stream, output_stream, modem: Modem):
        self.input_stream, self.output_stream, self.modem = input_stream, output_stream, modem
        self._samples: list[float] = []

    @classmethod
    def open(cls, input_device=None, output_device=None, config: ModemConfig | None = None):
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError("install sounddevice to use live audio") from exc
        config = config or ModemConfig()
        input_stream = sd.RawInputStream(samplerate=config.sample_rate, channels=1, dtype="int16", device=input_device, blocksize=1024)
        output_stream = sd.RawOutputStream(samplerate=config.sample_rate, channels=1, dtype="int16", device=output_device, blocksize=1024)
        input_stream.start()
        output_stream.start()
        return cls(input_stream, output_stream, Modem(config))

    def send(self, frame: Frame) -> None:
        samples = self.modem.encode(encode_frame(frame))
        pcm = b"".join(struct.pack("<h", max(-32767, min(32767, int(sample * 24000)))) for sample in samples)
        self.output_stream.write(pcm)

    def receive(self, timeout: float | None = None) -> Frame:
        # Live packet boundaries are found by successful modem decode; the modem
        # packet itself contains the frame length and CRC.
        import time
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError("audio receive timeout")
            raw, _ = self.input_stream.read(4096)
            self._samples.extend(value[0] / 32768.0 for value in struct.iter_unpack("<h", raw))
            try:
                packet = self.modem.decode(self._samples)
            except Exception:
                if len(self._samples) > self.modem.config.symbol_samples * 200:
                    self._samples = self._samples[-self.modem.config.symbol_samples * 2:]
                continue
            self._samples.clear()
            return decode_frame(packet)

    def close(self) -> None:
        self.input_stream.stop(); self.output_stream.stop()
        self.input_stream.close(); self.output_stream.close()
