from __future__ import annotations

import queue
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

from .protocol import Frame, FrameType, decode_file_info, encode_file_info
from .transfer import FileManifest, PartFile


@dataclass(frozen=True)
class TransferStats:
    bytes_sent: int = 0
    retransmissions: int = 0
    elapsed: float = 0.0


class MemoryDuplex:
    def __init__(self, incoming: queue.Queue, outgoing: queue.Queue):
        self.incoming, self.outgoing = incoming, outgoing

    @classmethod
    def pair(cls) -> tuple["MemoryDuplex", "MemoryDuplex"]:
        a, b = queue.Queue(), queue.Queue()
        return cls(a, b), cls(b, a)

    def send(self, frame: Frame) -> None:
        self.outgoing.put(frame)

    def receive(self, timeout: float | None = None) -> Frame:
        return self.incoming.get(timeout=timeout)


class SenderSession:
    def __init__(self, transport, chunk_size: int = 32 * 1024, timeout: float = 5.0):
        self.transport, self.chunk_size, self.timeout = transport, chunk_size, timeout

    def _wait_ack(self, session_id: int, sequence: int) -> None:
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"timeout waiting for ACK {sequence}")
            frame = self.transport.receive(remaining)
            if frame.session_id == session_id and frame.frame_type == FrameType.ACK and frame.ack >= sequence:
                return

    def run(self, path: str | Path, options=None) -> TransferStats:
        start = time.monotonic()
        path = Path(path)
        manifest = FileManifest.from_path(path, self.chunk_size)
        session_id = secrets.randbits(63)
        self.transport.send(Frame(FrameType.HELLO, session_id, 0, 0))
        self._wait_ack(session_id, 0)
        self.transport.send(Frame(FrameType.FILE_INFO, session_id, 0, 0, encode_file_info(manifest.name, manifest.size, manifest.chunk_size, manifest.sha256)))
        self._wait_ack(session_id, 0)
        sent = 0
        with path.open("rb") as handle:
            for sequence in range(manifest.chunks):
                payload = handle.read(manifest.chunk_size)
                self.transport.send(Frame(FrameType.DATA, session_id, sequence, 0, payload))
                self._wait_ack(session_id, sequence)
                sent += len(payload)
        self.transport.send(Frame(FrameType.FINISH, session_id, manifest.chunks, 0))
        self._wait_ack(session_id, manifest.chunks)
        return TransferStats(sent, 0, time.monotonic() - start)


class ReceiverSession:
    def __init__(self, transport, timeout: float = 5.0):
        self.transport, self.timeout = transport, timeout

    def run(self, output_dir: str | Path, resume: bool = False, options=None) -> TransferStats:
        start = time.monotonic()
        hello = self.transport.receive(self.timeout)
        if hello.frame_type != FrameType.HELLO:
            raise ValueError("expected HELLO")
        self.transport.send(Frame(FrameType.ACK, hello.session_id, 0, 0))
        info_frame = self.transport.receive(self.timeout)
        if info_frame.frame_type != FrameType.FILE_INFO:
            raise ValueError("expected FILE_INFO")
        info = decode_file_info(info_frame.payload)
        self.transport.send(Frame(FrameType.ACK, hello.session_id, 0, 0))
        manifest = FileManifest(info.name, info.size, info.chunk_size, info.sha256)
        part = PartFile.open(output_dir, manifest, resume=resume)
        while True:
            frame = self.transport.receive(self.timeout)
            if frame.session_id != hello.session_id:
                continue
            if frame.frame_type == FrameType.DATA:
                part.write_chunk(frame.sequence, frame.payload)
                self.transport.send(Frame(FrameType.ACK, hello.session_id, frame.sequence, frame.sequence))
            elif frame.frame_type == FrameType.FINISH:
                target = part.finish()
                self.transport.send(Frame(FrameType.ACK, hello.session_id, frame.sequence, frame.sequence))
                return TransferStats(manifest.size, 0, time.monotonic() - start)
            elif frame.frame_type == FrameType.ABORT:
                raise RuntimeError(frame.payload.decode("utf-8", "replace"))
