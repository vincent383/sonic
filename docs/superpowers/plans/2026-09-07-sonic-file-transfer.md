# Sonic Transfer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dependency-light Python CLI that reliably transfers one large file over a bidirectional audio cable using a small OFDM/QPSK modem and selective-repeat ARQ.

**Architecture:** Separate byte framing, ARQ, file persistence, modem, and audio-device layers. The first runnable implementation uses an in-memory/sample-array channel for deterministic tests, while the live path connects `sounddevice` RawStreams through bounded queues. File data travels one way and ACK/control frames travel the reverse way.

**Tech Stack:** Python 3.11+, standard library (`argparse`, `dataclasses`, `hashlib`, `struct`, `zlib`, `threading`, `queue`, `wave`), optional runtime dependency `sounddevice`, pytest for tests.

**Spec:** `docs/superpowers/specs/2026-09-07-sonic-file-transfer-design.md`

## Global Constraints

- Python 3.11 or higher.
- Runtime dependency is only `sounddevice`; protocol, CRC, file handling and tests use the standard library.
- Default audio format is 48,000Hz, signed 16-bit PCM, with one independent mono band per direction.
- Every received file must be verified with SHA-256 before atomic rename.
- Corruption and loss must be recoverable through CRC32, ACK/NACK and selective retransmission.
- Tests must include deterministic virtual-channel cases before live audio-device testing.

---

### Task 1: Project scaffold and public CLI skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/sonic_transfer/__init__.py`
- Create: `src/sonic_transfer/__main__.py`
- Create: `src/sonic_transfer/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces `python -m sonic_transfer devices|send|receive` parser and stable exit codes.

- [ ] **Step 1: Write the failing test**

```python
def test_devices_command_is_available(capsys):
    from sonic_transfer.cli import main
    assert main(["devices"]) == 0
    assert "audio" in capsys.readouterr().out.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_cli.py::test_devices_command_is_available`
Expected: FAIL because the package and parser do not exist.

- [ ] **Step 3: Write minimal implementation**

Create package metadata, a parser with `devices`, `send`, and `receive`, and make `devices` print a dependency-free message until the audio backend is implemented.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest -q tests/test_cli.py::test_devices_command_is_available`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml README.md src tests
git commit -m "feat: scaffold sonic transfer CLI"
```

### Task 2: Binary frame protocol and metadata

**Files:**
- Create: `src/sonic_transfer/protocol.py`
- Test: `tests/test_protocol.py`

**Interfaces:**
- `Frame(frame_type: FrameType, session_id: int, sequence: int, ack: int, payload: bytes)`.
- `encode_frame(frame: Frame) -> bytes`.
- `decode_frame(data: bytes) -> Frame`.
- `encode_file_info(name: str, size: int, chunk_size: int, sha256: bytes) -> bytes`.
- `decode_file_info(payload: bytes) -> FileInfo`.

- [ ] **Step 1: Write failing tests** for round-trip, CRC rejection, malformed length, UTF-8 names, and protocol-version rejection.
- [ ] **Step 2: Run `pytest -q tests/test_protocol.py` and confirm expected failures.**
- [ ] **Step 3: Implement fixed-endian header, enum types, payload limits, CRC32, and metadata validation with `struct`/`zlib`.
- [ ] **Step 4: Run the focused tests and then `pytest -q tests/test_protocol.py`; expect all pass.**
- [ ] **Step 5: Commit** with `feat: add framed transfer protocol`.

### Task 3: Selective-repeat ARQ state machine

**Files:**
- Create: `src/sonic_transfer/arq.py`
- Test: `tests/test_arq.py`

**Interfaces:**
- `SenderWindow(window_size: int, timeout: float)` with `queue(sequence, payload)`, `acknowledge(sequence)`, `due(now)`, and `complete`.
- `ReceiverWindow(window_size: int)` with `receive(sequence, payload) -> list[bytes]` and `ack_state() -> tuple[int, tuple[int, ...]]`.

- [ ] **Step 1: Write failing tests** for in-order delivery, out-of-order buffering, duplicate suppression, window limits, ACK advancement, and timeout retransmission.
- [ ] **Step 2: Run `pytest -q tests/test_arq.py` and confirm failures are due to missing implementation.**
- [ ] **Step 3: Implement bounded dictionaries/sets and monotonic cumulative ACK plus sparse missing sequence reporting.**
- [ ] **Step 4: Run focused tests and `pytest -q`; expect all current tests pass.**
- [ ] **Step 5: Commit** with `feat: add selective repeat ARQ`.

### Task 4: File streaming and resumable persistence

**Files:**
- Create: `src/sonic_transfer/transfer.py`
- Test: `tests/test_transfer.py`

**Interfaces:**
- `FileManifest.from_path(path, chunk_size) -> FileManifest`.
- `PartFile.open(directory, manifest, resume=False) -> PartFile`.
- `PartFile.write_chunk(sequence, payload)`, `PartFile.missing_ranges()`, and `PartFile.finish() -> Path`.

- [ ] **Step 1: Write failing tests** for manifest hash, non-aligned chunks, `.part` state, resume, duplicate chunks, hash mismatch, and atomic finalization.
- [ ] **Step 2: Run `pytest -q tests/test_transfer.py` and confirm failures.**
- [ ] **Step 3: Implement streaming SHA-256, JSON state sidecar, random-access chunk writes, fsync, and `os.replace` only after full hash verification.**
- [ ] **Step 4: Run focused tests including a generated multi-megabyte streaming fixture.**
- [ ] **Step 5: Commit** with `feat: add resumable file persistence`.

### Task 5: Deterministic OFDM/QPSK modem and virtual channel

**Files:**
- Create: `src/sonic_transfer/modem.py`
- Create: `src/sonic_transfer/virtual_channel.py`
- Test: `tests/test_modem.py`

**Interfaces:**
- `ModemConfig(sample_rate=48000, mode="fast")`.
- `Modem.encode(data: bytes) -> list[float]`.
- `Modem.decode(samples: list[float]) -> bytes`.
- `VirtualChannel(loss_rate=0.0, noise=0.0, frequency_offset=0.0).transmit(samples) -> list[float]`.

- [ ] **Step 1: Write failing tests** for byte round-trip, sync prefix, amplitude normalization, robust/fast configurations, and injected loss/noise producing explicit decode failure rather than silent corruption.
- [ ] **Step 2: Run `pytest -q tests/test_modem.py` and confirm failures.**
- [ ] **Step 3: Implement a small dependency-free modem: fixed pilot/preamble, real-valued orthogonal carriers, differential QPSK symbols, block CRC boundary, and bounded decoder diagnostics. Keep DSP loops in focused functions so the live audio layer can later replace the sample source.**
- [ ] **Step 4: Run focused modem tests and a stress test over at least 1MB of pseudo-random bytes without storing duplicate encoded file data.**
- [ ] **Step 5: Commit** with `feat: add dependency-light audio modem`.

### Task 6: Audio device adapter and session orchestration

**Files:**
- Create: `src/sonic_transfer/audio.py`
- Create: `src/sonic_transfer/session.py`
- Test: `tests/test_session.py`

**Interfaces:**
- `list_devices() -> list[dict[str, object]]`.
- `AudioDuplex.open(input_device, output_device, config) -> AudioDuplex`.
- `SenderSession.run(path, options) -> TransferStats`.
- `ReceiverSession.run(output_dir, options) -> TransferStats`.

- [ ] **Step 1: Write failing session tests** using a fake duplex audio transport for HELLO, FILE_INFO, DATA, ACK, FINISH, abort and resume.
- [ ] **Step 2: Run `pytest -q tests/test_session.py` and confirm failures.**
- [ ] **Step 3: Implement lazy `sounddevice` import, RawInputStream/RawOutputStream callbacks that only move fixed PCM blocks through bounded queues, and session threads that connect protocol/ARQ/file layers.**
- [ ] **Step 4: Run focused session tests and all tests; verify no sounddevice import is required for protocol-only tests.**
- [ ] **Step 5: Commit** with `feat: connect audio sessions and resume flow`.

### Task 7: Complete CLI, documentation, and verification

**Files:**
- Modify: `src/sonic_transfer/cli.py`
- Modify: `README.md`
- Modify: `pyproject.toml`
- Create: `tests/test_cli_integration.py`

**Interfaces:**
- CLI arguments expose device IDs, `--mode robust|fast`, `--resume`, and `--verbose`.

- [ ] **Step 1: Write failing CLI integration tests** for help, missing path, devices output, non-zero error handling, and fake-transport send/receive.
- [ ] **Step 2: Run focused tests and confirm failures.**
- [ ] **Step 3: Implement command wiring, logging, human-readable transfer stats, dependency installation notes, Windows/macOS permissions, loopback test instructions, and troubleshooting.**
- [ ] **Step 4: Run `pytest -q`, `python -m compileall -q src`, and `python -m sonic_transfer --help`; expect zero test failures and exit code 0 for help.**
- [ ] **Step 5: Commit** with `docs: document installation and audio setup`.

## Verification Checklist

- [ ] `pytest -q` passes with zero failures.
- [ ] `python -m compileall -q src` exits 0.
- [ ] CLI help and `devices` work without importing optional audio dependencies prematurely.
- [ ] Virtual-channel tests cover corruption/loss and prove no silent bad file is finalized.
- [ ] Resume tests prove transfer does not restart from byte zero.
- [ ] `git diff --check` is clean and `git status` shows only intentional committed project files.
