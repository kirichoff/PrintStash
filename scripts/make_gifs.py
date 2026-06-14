#!/usr/bin/env python3
"""Assemble screenshot frames into GIFs."""
from pathlib import Path
from PIL import Image

FRAMES_DIR = Path(__file__).parent.parent / "screenshots" / "gif-frames"
OUT_DIR = Path(__file__).parent.parent / "screenshots"


def make_gif(frame_paths: list[Path], output: Path, durations: list[int]) -> None:
    frames = [Image.open(p).convert("P", palette=Image.ADAPTIVE, colors=256) for p in frame_paths]
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        loop=0,
        duration=durations,
        optimize=True,
    )
    print(f"Saved {output} ({output.stat().st_size // 1024} KB, {len(frames)} frames)")


# --- 12-tag-filter.gif ---
make_gif(
    frame_paths=[
        FRAMES_DIR / "tagfilter-01.png",  # all models
        FRAMES_DIR / "tagfilter-02.png",  # car tag active
        FRAMES_DIR / "tagfilter-02.png",  # hold
        FRAMES_DIR / "tagfilter-01.png",  # cleared
        FRAMES_DIR / "tagfilter-03.png",  # skadis tag active
        FRAMES_DIR / "tagfilter-03.png",  # hold
        FRAMES_DIR / "tagfilter-04.png",  # cleared
    ],
    output=OUT_DIR / "12-tag-filter.gif",
    durations=[1200, 1800, 1800, 800, 1800, 1800, 800],
)

# --- 11-revision-compare.gif ---
make_gif(
    frame_paths=[
        FRAMES_DIR / "revcompare-01.png",  # revisions tab
        FRAMES_DIR / "revcompare-02.png",  # compare section visible
        FRAMES_DIR / "revcompare-03.png",  # same revision selected (both Rev 1)
        FRAMES_DIR / "revcompare-02.png",  # back to Rev2 vs Rev1
    ],
    output=OUT_DIR / "11-revision-compare.gif",
    durations=[1500, 2000, 2000, 1500],
)

# --- 00-demo.gif ---
make_gif(
    frame_paths=[
        FRAMES_DIR / "demo-01.png",  # home / asset grid
        FRAMES_DIR / "demo-02.png",  # model detail overview
        FRAMES_DIR / "demo-03.png",  # settings tab
        FRAMES_DIR / "demo-04.png",  # revisions tab
        FRAMES_DIR / "demo-05.png",  # files tab
        FRAMES_DIR / "demo-02.png",  # back to overview
    ],
    output=OUT_DIR / "00-demo.gif",
    durations=[2000, 2200, 2200, 2200, 2200, 1500],
)
