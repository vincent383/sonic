from __future__ import annotations

import argparse


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
        print("Audio devices are available after installing sounddevice.")
        return 0
    print("Transfer sessions are not wired yet; use the library API.")
    return 2
