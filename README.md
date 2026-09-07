# Sonic Transfer

Reliable single-file transfer over a full-duplex audio crossover cable.

## Install

Python 3.11+ is required. Install the package and test tools with:

```text
python -m pip install -e '.[test]'
```

The live audio adapter uses `sounddevice`/PortAudio. On macOS grant Terminal (or the Python launcher) Microphone permission. On Windows select the cable's input and output devices in the system sound panel and disable aggressive noise suppression/automatic gain if possible.

## Usage

```text
python -m sonic_transfer devices
python -m sonic_transfer receive ./received --mode robust --resume
python -m sonic_transfer send ./large-file.bin --mode robust
```

Run the receiver first. Use `devices` to find device names/indices, then pass `--input-device` and `--output-device` to both processes when the defaults are wrong. The receiver writes a `.part` file and JSON state beside it; rerun with `--resume` after an interruption. A completed file is SHA-256 checked before being renamed.

The modem and protocol tests use an in-memory signal path and do not need a physical cable:

```text
pytest -q
python -m compileall -q src
```

This initial implementation favors a small, inspectable dependency footprint. Actual cable throughput depends on sound cards, cable quality, gain, and noise; use robust mode when fast mode produces retransmissions.
