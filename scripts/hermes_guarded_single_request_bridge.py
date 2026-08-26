#!/usr/bin/env python3
"""Candidate Hermes bridge with a hard one-physical-request ceiling.

Its bytes are inert until included in a separately approved activation packet.
"""

from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

from x_factory.phase4_transport_guard_v0_1 import install_into_hermes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("atlas", "aria", "mason", "vera"), required=True)
    parser.add_argument("--factory-root", type=Path, required=True)
    parser.add_argument("--prompt-file", type=Path, required=True)
    args = parser.parse_args()

    prompt_file = args.prompt_file.resolve(strict=True)
    factory_root = args.factory_root.resolve(strict=True)
    prompt_file.relative_to(factory_root)
    prompt = prompt_file.read_text(encoding="utf-8")

    install_into_hermes()
    sys.argv = [
        "hermes",
        "--profile", args.profile,
        "chat", "-Q",
        "--provider", "openai-codex",
        "--model", "gpt-5.6-luna",
        "--reasoning", "low",
        "--max-turns", "1",
        "--source", "tool",
        "--in", str(factory_root),
        "-q", prompt,
    ]
    runpy.run_module("hermes_cli.main", run_name="__main__")


if __name__ == "__main__":
    main()
