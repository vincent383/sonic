from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileManifest:
    name: str
    size: int
    chunk_size: int
    sha256: bytes

    @classmethod
    def from_path(cls, path: str | Path, chunk_size: int = 32 * 1024) -> "FileManifest":
        path = Path(path)
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return cls(path.name, path.stat().st_size, chunk_size, digest.digest())

    @property
    def chunks(self) -> int:
        return (self.size + self.chunk_size - 1) // self.chunk_size


class PartFile:
    def __init__(self, directory: Path, manifest: FileManifest, path: Path, state_path: Path, received: set[int]):
        self.directory, self.manifest, self.path, self.state_path = directory, manifest, path, state_path
        self.received = received

    @classmethod
    def open(cls, directory: str | Path, manifest: FileManifest, resume: bool = False) -> "PartFile":
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        safe_name = Path(manifest.name).name
        path = directory / (safe_name + ".part")
        state_path = directory / (safe_name + ".part.json")
        received: set[int] = set()
        if resume and state_path.exists() and path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            expected = {"name": safe_name, "size": manifest.size, "chunk_size": manifest.chunk_size, "sha256": manifest.sha256.hex()}
            if all(state.get(k) == v for k, v in expected.items()):
                received = set(state.get("received", []))
        if not path.exists() or not resume:
            with path.open("wb") as handle:
                handle.truncate(manifest.size)
        return cls(directory, manifest, path, state_path, received)

    def _save_state(self) -> None:
        state = {"name": self.manifest.name, "size": self.manifest.size, "chunk_size": self.manifest.chunk_size,
                 "sha256": self.manifest.sha256.hex(), "received": sorted(self.received)}
        tmp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        tmp.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.state_path)

    def write_chunk(self, sequence: int, payload: bytes) -> None:
        if sequence < 0 or sequence >= self.manifest.chunks:
            raise ValueError("chunk sequence out of range")
        expected = min(self.manifest.chunk_size, self.manifest.size - sequence * self.manifest.chunk_size)
        if len(payload) != expected:
            raise ValueError("invalid chunk size")
        with self.path.open("r+b") as handle:
            handle.seek(sequence * self.manifest.chunk_size)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        self.received.add(sequence)
        self._save_state()

    def missing_ranges(self) -> list[tuple[int, int]]:
        missing = [i for i in range(self.manifest.chunks) if i not in self.received]
        ranges: list[tuple[int, int]] = []
        for value in missing:
            if ranges and value == ranges[-1][1] + 1:
                ranges[-1] = (ranges[-1][0], value)
            else:
                ranges.append((value, value))
        return ranges

    def finish(self) -> Path:
        if self.missing_ranges():
            raise ValueError("file is incomplete")
        digest = hashlib.sha256()
        with self.path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        if digest.digest() != self.manifest.sha256:
            raise ValueError("SHA-256 mismatch")
        target = self.directory / self.manifest.name
        if target.exists() and target != self.path:
            raise FileExistsError(target)
        os.replace(self.path, target)
        self.state_path.unlink(missing_ok=True)
        return target
