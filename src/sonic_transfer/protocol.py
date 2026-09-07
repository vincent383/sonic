from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from enum import IntEnum

MAGIC = b"SFT1"
VERSION = 1
MAX_PAYLOAD = 64 * 1024
HEADER = struct.Struct("!4sBBIQQI")
CRC = struct.Struct("!I")


class FrameType(IntEnum):
    HELLO = 1
    FILE_INFO = 2
    DATA = 3
    ACK = 4
    NACK = 5
    FINISH = 6
    FINISH_ACK = 7
    ABORT = 8
    RESUME = 9


@dataclass(frozen=True)
class Frame:
    frame_type: FrameType
    session_id: int
    sequence: int
    ack: int
    payload: bytes = b""


@dataclass(frozen=True)
class FileInfo:
    name: str
    size: int
    chunk_size: int
    sha256: bytes


def encode_frame(frame: Frame) -> bytes:
    payload = bytes(frame.payload)
    if len(payload) > MAX_PAYLOAD:
        raise ValueError("payload too large")
    try:
        kind = FrameType(frame.frame_type)
    except ValueError as exc:
        raise ValueError("unknown frame type") from exc
    body = HEADER.pack(MAGIC, VERSION, int(kind), frame.session_id, frame.sequence, frame.ack, len(payload)) + payload
    return body + CRC.pack(zlib.crc32(body) & 0xFFFFFFFF)


def decode_frame(data: bytes) -> Frame:
    if len(data) < HEADER.size + CRC.size:
        raise ValueError("frame too short")
    header = data[:HEADER.size]
    magic, version, kind, session, sequence, ack, length = HEADER.unpack(header)
    if magic != MAGIC or version != VERSION:
        raise ValueError("unsupported protocol version")
    if length > MAX_PAYLOAD or len(data) != HEADER.size + length + CRC.size:
        raise ValueError("invalid frame length")
    expected = CRC.unpack(data[-CRC.size:])[0]
    if zlib.crc32(data[:-CRC.size]) & 0xFFFFFFFF != expected:
        raise ValueError("CRC mismatch")
    try:
        frame_type = FrameType(kind)
    except ValueError as exc:
        raise ValueError("unknown frame type") from exc
    return Frame(frame_type, session, sequence, ack, data[HEADER.size:-CRC.size])


def encode_file_info(name: str, size: int, chunk_size: int, sha256: bytes) -> bytes:
    name_bytes = name.encode("utf-8")
    if not 0 <= size <= (1 << 63) or not 1 <= chunk_size <= MAX_PAYLOAD or len(sha256) != 32:
        raise ValueError("invalid file metadata")
    if len(name_bytes) > 1024:
        raise ValueError("file name too long")
    return struct.pack("!HQI32s", len(name_bytes), size, chunk_size, sha256) + name_bytes


def decode_file_info(payload: bytes) -> FileInfo:
    prefix = struct.calcsize("!HQI32s")
    if len(payload) < prefix:
        raise ValueError("file metadata too short")
    name_len, size, chunk_size, digest = struct.unpack("!HQI32s", payload[:prefix])
    name_bytes = payload[prefix:]
    if name_len != len(name_bytes) or name_len > 1024:
        raise ValueError("invalid file name length")
    try:
        name = name_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("file name is not UTF-8") from exc
    if not name or "/" in name or "\\" in name or not 1 <= chunk_size <= MAX_PAYLOAD:
        raise ValueError("invalid file metadata")
    return FileInfo(name, size, chunk_size, digest)
