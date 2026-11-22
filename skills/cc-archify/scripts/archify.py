#!/usr/bin/env python3
"""Apply personal source-display rules to a temporary Archify copy."""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", required=True, type=Path)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.arguments:
        parser.error("supply an Archify command after --upstream PATH")
    upstream = args.upstream.expanduser().resolve()
    for relative in ("SKILL.md", "assets/template.html", "bin/archify.mjs"):
        if not (upstream / relative).is_file():
            parser.error(f"missing installed Archify file: {upstream / relative}")
    for executable in ("node", "patch"):
        if shutil.which(executable) is None:
            parser.error(f"required executable is unavailable: {executable}")

    patch = Path(__file__).resolve().parent.parent / "assets/source-display.patch"
    with tempfile.TemporaryDirectory(prefix="cc-archify-") as temporary:
        runtime = Path(temporary) / "archify"
        shutil.copytree(upstream, runtime, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        result = subprocess.run(
            ["patch", "--batch", "--forward", "--fuzz=0", "-p1", "-i", str(patch)],
            cwd=runtime, capture_output=True, text=True,
        )
        if result.returncode:
            print(
                "cc-archify: source-display patch is incompatible with this Archify template. "
                "No Archify command was run; adapt assets/source-display.patch before retrying.",
                file=sys.stderr,
            )
            print(result.stdout + result.stderr, file=sys.stderr)
            return 2
        return subprocess.run(["node", str(runtime / "bin/archify.mjs"), *args.arguments]).returncode


if __name__ == "__main__":
    raise SystemExit(main())
