#!/usr/bin/env python3
"""Build a JSON array of GitLab release asset links from file paths.

Usage:
    python3 scripts/build-asset-links.py --base-url URL [FILE:LABEL:TYPE ...]

Each positional argument is colon-separated: local_path:link_name:link_type
Only files that exist are included. Outputs a JSON array to stdout.

Example:
    python3 scripts/build-asset-links.py \
        --base-url "https://gitlab.example.com/api/v4/projects/1/packages/generic/myproj/1.0.0" \
        "output/fab.zip:Fabrication package:package" \
        "output/schematic.pdf:Schematic PDF:other"
"""

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("files", nargs="*")
    args = parser.parse_args()

    links = []
    uploaded = []

    for entry in args.files:
        parts = entry.split(":", 2)
        if len(parts) != 3:
            print(f"Warning: skipping malformed entry: {entry}", file=sys.stderr)
            continue

        local_path, name, link_type = parts
        if not Path(local_path).exists():
            continue

        filename = Path(local_path).name
        url = f"{args.base_url}/{filename}"
        links.append({"name": name, "url": url, "link_type": link_type})
        uploaded.append({"local_path": local_path, "url": url, "filename": filename})

    # Output: first line is the asset links JSON, then one upload entry per line
    result = {"links": links, "uploads": uploaded}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
