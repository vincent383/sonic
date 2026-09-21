from __future__ import annotations

import getpass
import hashlib
import os
import struct
import tempfile
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC = b"SENC1"
VERSION = 1
CHUNK_SIZE = 1024 * 1024
SALT_SIZE = 16
NONCE_PREFIX_SIZE = 8
TAG_SIZE = 16
HEADER = struct.Struct("!5sB16s8sIH")
RECORD = struct.Struct("!II")


class CryptoError(ValueError):
    """Raised when an encrypted file cannot be authenticated or parsed."""


class OutputExistsError(FileExistsError):
    """Raised instead of silently overwriting an existing output file."""


def _derive_key(password: str, salt: bytes) -> bytes:
    if not isinstance(password, str) or not password:
        raise ValueError("password must not be empty")
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(password.encode("utf-8"))


def _safe_name(name: str) -> str:
    candidate = Path(name).name
    if not candidate or candidate != name or name in {".", ".."}:
        raise CryptoError("invalid stored file name")
    return candidate


def _prepare_output(output: Path) -> None:
    if output.exists():
        raise OutputExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)


def _commit_temp(temp_name: str, output: Path) -> None:
    try:
        os.link(temp_name, output)
    except FileExistsError as exc:
        raise OutputExistsError(output) from exc
    finally:
        Path(temp_name).unlink(missing_ok=True)


def encrypt_file(source: str | Path, output: str | Path, password: str, chunk_size: int = CHUNK_SIZE) -> Path:
    source = Path(source)
    output = Path(output)
    if chunk_size < 4096 or chunk_size > 16 * 1024 * 1024:
        raise ValueError("chunk size must be between 4096 and 16 MiB")
    if source.resolve() == output.resolve():
        raise ValueError("input and output must be different files")
    _prepare_output(output)
    name = source.name.encode("utf-8")
    if len(name) > 65535:
        raise ValueError("file name is too long")
    salt = os.urandom(SALT_SIZE)
    nonce_prefix = os.urandom(NONCE_PREFIX_SIZE)
    header = HEADER.pack(MAGIC, VERSION, salt, nonce_prefix, chunk_size, len(name)) + name
    cipher = ChaCha20Poly1305(_derive_key(password, salt))
    temp_name = ""
    try:
        fd, temp_name = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
        with os.fdopen(fd, "wb") as destination, source.open("rb") as source_file:
            destination.write(header)
            for index in range(0, 2**32):
                plaintext = source_file.read(chunk_size)
                if not plaintext:
                    break
                record = RECORD.pack(index, len(plaintext))
                nonce = nonce_prefix + struct.pack("!I", index)
                destination.write(record)
                destination.write(cipher.encrypt(nonce, plaintext, header + record))
            destination.flush()
            os.fsync(destination.fileno())
        _commit_temp(temp_name, output)
        temp_name = ""
        return output
    finally:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)


def decrypt_file(source: str | Path, output: str | Path | None, password: str) -> Path:
    source = Path(source)
    output = Path(output) if output is not None else source.with_suffix("")
    _prepare_output(output)
    temp_name = ""
    try:
        with source.open("rb") as encrypted:
            fixed = encrypted.read(HEADER.size)
            if len(fixed) != HEADER.size:
                raise CryptoError("encrypted header is truncated")
            magic, version, salt, nonce_prefix, chunk_size, name_length = HEADER.unpack(fixed)
            if magic != MAGIC or version != VERSION:
                raise CryptoError("unsupported encrypted file version")
            name_bytes = encrypted.read(name_length)
            if len(name_bytes) != name_length:
                raise CryptoError("encrypted file name is truncated")
            try:
                _safe_name(name_bytes.decode("utf-8"))
            except UnicodeDecodeError as exc:
                raise CryptoError("encrypted file name is invalid UTF-8") from exc
            if not 4096 <= chunk_size <= 16 * 1024 * 1024:
                raise CryptoError("invalid encrypted chunk size")
            header = fixed + name_bytes
            cipher = ChaCha20Poly1305(_derive_key(password, salt))
            fd, temp_name = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
            with os.fdopen(fd, "wb") as destination:
                expected_index = 0
                while True:
                    record = encrypted.read(RECORD.size)
                    if not record:
                        break
                    if len(record) != RECORD.size:
                        raise CryptoError("encrypted record is truncated")
                    index, plaintext_length = RECORD.unpack(record)
                    if index != expected_index or not 0 < plaintext_length <= chunk_size:
                        raise CryptoError("invalid encrypted record")
                    ciphertext = encrypted.read(plaintext_length + TAG_SIZE)
                    if len(ciphertext) != plaintext_length + TAG_SIZE:
                        raise CryptoError("encrypted record payload is truncated")
                    nonce = nonce_prefix + struct.pack("!I", index)
                    try:
                        plaintext = cipher.decrypt(nonce, ciphertext, header + record)
                    except InvalidTag as exc:
                        raise CryptoError("wrong password or modified encrypted file") from exc
                    destination.write(plaintext)
                    expected_index += 1
                destination.flush()
                os.fsync(destination.fileno())
        _commit_temp(temp_name, output)
        temp_name = ""
        return output
    finally:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)


def prompt_password(confirm: bool = False) -> str:
    password = getpass.getpass("Password: ")
    if confirm:
        if password != getpass.getpass("Confirm password: "):
            raise CryptoError("passwords do not match")
    return password
