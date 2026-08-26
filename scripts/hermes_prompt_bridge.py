#!/usr/bin/env python3
"""Invoke Hermes with a prompt loaded in-process to avoid Windows argv limits."""

from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--reasoning", required=True)
    parser.add_argument("--factory-root", type=Path, required=True)
    parser.add_argument("--prompt-file", type=Path, required=True)
    args = parser.parse_args()

    prompt = args.prompt_file.read_text(encoding="utf-8")
    sys.argv = [
        "hermes",
        "--profile", args.profile,
        "chat", "-Q",
        "--reasoning", args.reasoning,
        "--max-turns", "4",
        "--source", "tool",
        "--in", str(args.factory_root),
        "-q", prompt,
    ]
    runpy.run_module("hermes_cli.main", run_name="__main__")


if __name__ == "__main__":
    main()
