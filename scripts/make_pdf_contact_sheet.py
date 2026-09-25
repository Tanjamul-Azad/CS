"""Create compact contact sheets from rendered paper pages for visual QA."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--per-sheet", type=int, default=6)
    args = parser.parse_args()
    pages = sorted(args.directory.glob("page-*.png"))
    if not pages:
        raise SystemExit("no page-*.png images found")
    for start in range(0, len(pages), args.per_sheet):
        group = pages[start:start + args.per_sheet]
        sheet = Image.new("RGB", (1240, 2460), "white")
        draw = ImageDraw.Draw(sheet)
        for index, path in enumerate(group):
            image = ImageOps.contain(Image.open(path).convert("RGB"), (600, 800))
            x = (index % 2) * 620
            y = (index // 2) * 820
            sheet.paste(image, (x, y))
            draw.rectangle((x, y, x + 90, y + 24), fill="white")
            draw.text((x + 5, y + 5), path.stem, fill="red")
        destination = args.directory / f"contact-{start // args.per_sheet + 1}.png"
        sheet.save(destination)
        print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

