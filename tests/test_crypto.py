import hashlib

import pytest


def test_encrypt_decrypt_round_trip_preserves_bytes_and_filename(tmp_path):
    from sonic_transfer.crypto import decrypt_file, encrypt_file

    source = tmp_path / "中文 文件.bin"
    source.write_bytes(bytes(range(256)) * 9000)
    encrypted = tmp_path / "payload.senc"
    restored = tmp_path / "restored.bin"

    encrypt_file(source, encrypted, "correct horse")
    decrypt_file(encrypted, restored, "correct horse")

    assert restored.read_bytes() == source.read_bytes()
    assert hashlib.sha256(restored.read_bytes()).digest() == hashlib.sha256(source.read_bytes()).digest()


def test_wrong_password_and_tampering_are_rejected(tmp_path):
    from sonic_transfer.crypto import CryptoError, decrypt_file, encrypt_file

    source = tmp_path / "source.bin"
    encrypted = tmp_path / "source.senc"
    source.write_bytes(b"secret data")
    encrypt_file(source, encrypted, "password")

    with pytest.raises(CryptoError):
        decrypt_file(encrypted, tmp_path / "wrong.bin", "not password")

    content = bytearray(encrypted.read_bytes())
    content[-1] ^= 0x01
    encrypted.write_bytes(content)
    with pytest.raises(CryptoError):
        decrypt_file(encrypted, tmp_path / "tampered.bin", "password")


def test_existing_output_is_not_overwritten(tmp_path):
    from sonic_transfer.crypto import OutputExistsError, encrypt_file

    source = tmp_path / "source.bin"
    encrypted = tmp_path / "source.senc"
    source.write_bytes(b"one")
    encrypted.write_bytes(b"already here")
    with pytest.raises(OutputExistsError):
        encrypt_file(source, encrypted, "password")
