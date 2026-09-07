import pytest


def test_frame_round_trip_and_crc():
    from sonic_transfer.protocol import Frame, FrameType, decode_frame, encode_frame

    frame = Frame(FrameType.DATA, 12, 3, 2, b"hello")
    assert decode_frame(encode_frame(frame)) == frame
    broken = bytearray(encode_frame(frame))
    broken[-1] ^= 1
    with pytest.raises(ValueError, match="CRC"):
        decode_frame(bytes(broken))


def test_file_info_round_trip_and_validation():
    from sonic_transfer.protocol import decode_file_info, encode_file_info

    digest = bytes(range(32))
    info = decode_file_info(encode_file_info("测试.bin", 123, 4096, digest))
    assert (info.name, info.size, info.chunk_size, info.sha256) == ("测试.bin", 123, 4096, digest)
    with pytest.raises(ValueError):
        encode_file_info("x", 1, 1, b"short")
