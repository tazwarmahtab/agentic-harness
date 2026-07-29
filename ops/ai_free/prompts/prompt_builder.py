#!/usr/bin/env python3
"""
Deterministic prompt generator — builds prompts from template + keyword bank.
Netso mode: prompts are pre-baked with exact brand facts, so this just picks
a template and appends the canonical style anchor.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Literal

from ops.ai_free.styles.generation_style_guide import mastermind_prompt_bank

Channel = Literal[
    "netso_product_photography",
    "netso_hero_banners",
    "netso_social_carousels",
    "netso_pitch_deck_slides",
    "netso_marketing_assets",
    "netso_editorial_content",
    "netso_infographics",
]


def build_prompt(
    channel: Channel,
    *,
    style_anchor: str = "Netso Energy brand style, deep navy and solar amber accent, clean modern executive",
) -> str:
    templates = mastermind_prompt_bank[channel]
    template = random.choice(templates)
    return f"{template}. Global style anchor: {style_anchor}"


def generate_for_channel(
    channel: Channel,
    *,
    width: int = 1024,
    height: int = 1024,
    model: str = "flux",
    seed: int | None = None,
    filename: str | None = None,
    out_dir: str | Path = "/tmp/pollinations_bench",
) -> Path:
    from ops.ai_free.image import generate_image

    prompt = build_prompt(channel)
    if filename is None:
        stem = f"{channel}_{width}x{height}"
        if seed is not None:
            stem += f"_seed{seed}"
        filename = f"{stem}.jpg"
    return generate_image(
        prompt,
        width=width,
        height=height,
        model=model,
        seed=seed,
        out_dir=out_dir,
        filename=filename,
    )
