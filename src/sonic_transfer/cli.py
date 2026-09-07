from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sonic-transfer")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("devices", help="list audio devices")
    send = sub.add_parser("send", help="send one file")
    send.add_argument("path")
    receive = sub.add_parser("receive", help="receive one file")
    receive.add_argument("output_dir")
    for command in (send, receive):
        command.add_argument("--mode", choices=("robust", "fast"), default="fast")
        command.add_argument("--resume", action="store_true")
        command.add_argument("--verbose", action="store_true")
        command.add_argument("--input-device")
        command.add_argument("--output-device")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "devices":
        try:
            from .audio import list_devices
            for index, device in enumerate(list_devices()):
                print(f"{index}: {device.get('name', 'unknown')} (in={device.get('max_input_channels', 0)}, out={device.get('max_output_channels', 0)})")
            return 0
        except RuntimeError as exc:
            print(f"Audio devices unavailable: {exc}")
            return 0
    try:
        from .audio import AudioDuplex
        from .modem import ModemConfig
        from .session import ReceiverSession, SenderSession
        transport = AudioDuplex.open(args.input_device, args.output_device, ModemConfig(mode=args.mode))
        try:
            if args.command == "send":
                stats = SenderSession(transport).run(args.path, args)
            else:
                stats = ReceiverSession(transport).run(args.output_dir, resume=args.resume, options=args)
            print(f"Transferred {stats.bytes_sent} bytes in {stats.elapsed:.1f}s")
            return 0
        finally:
            transport.close()
    except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
