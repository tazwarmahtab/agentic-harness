"""
Free image generation helper — Pollinations.ai fallback.

This exists because the real Higgsfield free tier and the provided Banana key both
return insufficient-credits errors. It gives us a keyless, billed-free path for
light benchmarking until a real provider/credits are available.
"""

from __future__ import annotations

import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Literal

AspectRatio = Literal[
    "1:1",
    "1:4",
    "1:8",
    "2:3",
    "3:2",
    "3:4",
    "4:1",
    "4:3",
    "4:5",
    "5:4",
    "8:1",
    "9:16",
    "16:9",
    "21:9",
    "auto",
]

Resolution = Literal["0.5K", "1K", "2K", "4K"]


def generate_image(
    prompt: str,
    *,
    width: int = 1024,
    height: int = 1024,
    model: str = "flux",
    seed: int | None = None,
    nologo: bool = True,
    out_dir: str | Path = "/tmp/pollinations_bench",
    filename: str | None = None,
) -> Path:
    """Generate one image and return the saved Path."""

    safe = urllib.parse.quote(prompt)
    params = [f"width={width}", f"height={height}", f"model={model}"]
    if seed is not None:
        params.append(f"seed={seed}")
    if nologo:
        params.append("nologo=true")
    query = "&".join(params)
    url = f"https://image.pollinations.ai/prompt/{safe}?{query}"

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / (filename or f"{model}_{width}x{height}.jpg")

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        data = r.read()

    target.write_bytes(data)
    return target
