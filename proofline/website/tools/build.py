#!/usr/bin/env python3
"""Build the Proofline website: copy src/ -> dist/ with light HTML minification.

Stdlib only. No dependencies, no network. The site is already deployable as
plain files; this step just produces a tidy, comment-free dist/ tree.

Usage:
    python3 tools/build.py            # writes ./dist
    python3 tools/build.py --out X    # writes ./X
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = ROOT / "src"

_HTML_COMMENT = re.compile(r"<!--(?!\[if).*?-->", re.DOTALL)
_BETWEEN_TAGS_WS = re.compile(r">\s+<")
_RUNS_OF_WS = re.compile(r"[ \t]*\n[ \t]*")


def minify_html(text: str) -> str:
    text = _HTML_COMMENT.sub("", text)
    text = _RUNS_OF_WS.sub("\n", text)
    text = _BETWEEN_TAGS_WS.sub("><", text)
    return text.strip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist")
    args = ap.parse_args()

    if not SRC.is_dir():
        print(f"error: {SRC} not found", file=sys.stderr)
        return 1

    out = (ROOT / args.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    count = 0
    for path in sorted(SRC.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(SRC)
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".html":
            dest.write_text(minify_html(path.read_text(encoding="utf-8")), encoding="utf-8")
        else:
            shutil.copy2(path, dest)
        count += 1
        print(f"  {rel}")

    print(f"\nbuilt {count} files -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
