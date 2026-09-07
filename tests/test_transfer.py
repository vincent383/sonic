import hashlib

import pytest


def test_part_file_resumes_and_atomically_finishes(tmp_path):
    from sonic_transfer.transfer import FileManifest, PartFile

    source = tmp_path / "source.bin"
    source.write_bytes(b"abcdefghij")
    source_manifest = FileManifest.from_path(source, chunk_size=4)
    manifest = FileManifest("received.bin", source_manifest.size, source_manifest.chunk_size, source_manifest.sha256)
    part = PartFile.open(tmp_path, manifest)
    part.write_chunk(0, b"abcd")
    part.write_chunk(2, b"ij")
    assert part.missing_ranges() == [(1, 1)]
    resumed = PartFile.open(tmp_path, manifest, resume=True)
    resumed.write_chunk(1, b"efgh")
    assert resumed.finish().read_bytes() == source.read_bytes()


def test_finish_rejects_hash_mismatch(tmp_path):
    from sonic_transfer.transfer import FileManifest, PartFile

    manifest = FileManifest("x.bin", 3, 3, hashlib.sha256(b"yes").digest())
    part = PartFile.open(tmp_path, manifest)
    part.write_chunk(0, b"no!")
    with pytest.raises(ValueError, match="SHA-256"):
        part.finish()
