from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an optimized README GIF from PNG frames.")
    parser.add_argument("frames", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--duration", type=int, default=150)
    parser.add_argument("--colors", type=int, default=128)
    args = parser.parse_args()

    paths = sorted(args.frames.glob("*.png"))
    if not paths:
        raise SystemExit(f"No PNG frames found in {args.frames}")

    frames: list[Image.Image] = []
    for path in paths:
        with Image.open(path) as source:
            image = source.convert("RGB")
            height = round(image.height * args.width / image.width)
            image = image.resize((args.width, height), Image.Resampling.LANCZOS)
            frames.append(
                image.quantize(
                    colors=args.colors,
                    method=Image.Quantize.MEDIANCUT,
                    dither=Image.Dither.FLOYDSTEINBERG,
                )
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        args.output,
        save_all=True,
        append_images=frames[1:],
        duration=args.duration,
        loop=0,
        optimize=True,
        disposal=2,
    )


if __name__ == "__main__":
    main()
