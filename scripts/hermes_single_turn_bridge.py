#!/usr/bin/env python3
"""Invoke one governed Hermes stage with a one-iteration hard ceiling.

This bridge is not called by the inactive runner.  It is a candidate transport
component whose bytes must be approved before any use.
"""

from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("atlas", "aria", "mason", "vera"), required=True)
    parser.add_argument("--factory-root", type=Path, required=True)
    parser.add_argument("--prompt-file", type=Path, required=True)
    args = parser.parse_args()

    prompt = args.prompt_file.read_text(encoding="utf-8")
    sys.argv = [
        "hermes",
        "--profile", args.profile,
        "chat", "-Q",
        "--provider", "openai-codex",
        "--model", "gpt-5.6-luna",
        "--reasoning", "low",
        "--max-turns", "1",
        "--source", "tool",
        "--in", str(args.factory_root),
        "-q", prompt,
    ]
    runpy.run_module("hermes_cli.main", run_name="__main__")


if __name__ == "__main__":
    main()

