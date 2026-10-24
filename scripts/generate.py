#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
yy-rednote-img : Xiaohongshu image pipeline main script.

Two execution modes:
  * agent-mode (default) — Pure Python: builds structured prompts, writes a tasks.json
                            and validates images placed into the input folder by the host
                            agent (e.g. TRAE calling its GenerateImage tool).
  * api-mode              — Requires API keys: calls OpenAI DALL·E 3 / FAL FLUX directly.

This separation keeps the script runnable with zero API keys and testable offline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Pure-Python PNG validator — avoids requiring Pillow for dry-run / agent-mode.
# Pillow is still preferred (and used automatically when available) for ratio
# validation because it decodes the IHDR chunk correctly across variants.
# ---------------------------------------------------------------------------

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
PNG_MIN_BYTES = 50 * 1024  # 50 KB — anything smaller is almost always corrupt.


def _png_meta_fallback(data: bytes) -> Optional[Tuple[int, int]]:
    """Decode PNG width / height from the IHDR chunk without Pillow.

    Returns (width, height) or None if parse fails.  Layout:
      [0:8]   magic
      [8:12]  chunk length (big endian)
      [12:16] chunk type == b'IHDR'
      [16:20] width  (BE uint32)
      [20:24] height (BE uint32)
    """
    if len(data) < 24 or data[:8] != PNG_MAGIC:
        return None
    chunk_type = data[12:16]
    if chunk_type != b"IHDR":
        return None
    import struct
    try:
        w, h = struct.unpack(">II", data[16:24])
    except struct.error:
        return None
    if w <= 0 or h <= 0 or w > 20000 or h > 20000:
        return None
    return w, h


def get_image_size(path: Path) -> Optional[Tuple[int, int]]:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    try:
        from PIL import Image  # type: ignore
        with Image.open(path) as im:
            return im.size  # (w, h)
    except Exception:
        return _png_meta_fallback(data)


def validate_png(path: Path, min_bytes: int = PNG_MIN_BYTES) -> Tuple[bool, str]:
    """Return (ok, reason)."""
    if not path.exists():
        return False, "missing file"
    size = path.stat().st_size
    if size < min_bytes:
        return False, f"too small ({size} < {min_bytes})"
    try:
        with path.open("rb") as fh:
            head = fh.read(8)
    except OSError as exc:
        return False, f"read error: {exc}"
    if head != PNG_MAGIC:
        return False, f"bad PNG header: {head!r}"
    return True, "ok"


def _ratio_to_float(r: str) -> float:
    a, b = r.split(":")
    return int(a) / int(b)


def validate_ratio(path: Path, target_ratio: str, tol_pct: float = 1.0) -> Tuple[bool, str]:
    dims = get_image_size(path)
    if dims is None:
        return False, "cannot decode dimensions"
    w, h = dims
    actual = w / h
    target = _ratio_to_float(target_ratio)
    err_pct = abs(actual - target) / target * 100.0
    if err_pct > tol_pct:
        return False, f"ratio off {err_pct:.2f}% (image {w}x{h} -> 1/{1/actual:.3f}, want 1/{1/target:.3f})"
    return True, f"ok ({w}x{h}, err {err_pct:.3f}%)"


# ---------------------------------------------------------------------------
# Preset loading + prompt building.  These are the two units covered by tests.
# ---------------------------------------------------------------------------

DEFAULT_PRESET_PATH = Path(__file__).resolve().parent.parent / "styles" / "presets.json"

# Rough topic visualisation map — when the topic keyword matches we add a
# ready-made visual scene block.  This prevents the "skincare three steps ->
# model doesn't know what to draw" problem.
_TOPIC_VISUAL_KEYS: Dict[str, str] = {
    "skincare": "glass cosmetic bottles on cream marble, toner cotton pad, dropper with serum drop, next to moisturizer jar, fingers gently patting cheek skin",
    "skin care": "glass cosmetic bottles on cream marble, toner cotton pad, dropper with serum drop, next to moisturizer jar",
    "lipstick": "swatches of lipstick on forearm next to open tube, compact mirror, lip brush, vanity table with soft ring light",
    "makeup": "cosmetic palette with brushes, compact powder, mascara wand, eyeliner on vanity table with led ring light",
    "outfit": "flat lay of weekday outfits, blazer, silk blouse, leather loafers, mini handbag, watch laid on warm beige linen",
    "fashion": "flat lay of curated garments with matching accessories, mood board arrangement on linen",
    "coffee": "latte art heart on ceramic cup, open croissant, notebook page with handwriting, top view cafe table",
    "dessert": "close up of plated dessert, fork with a bite, steam rising, crumbs on plate, linen napkin and silver cutlery",
    "food": "overhead shot of plated meal with side dishes, steam, chopsticks, natural window light",
    "study": "pastel yellow open notebook with handwritten vocabulary, apple pencil, retro dictionary, cup of matcha latte, flat lay on wooden desk",
    "english": "pastel yellow open notebook with handwritten vocabulary, apple pencil, vintage oxford dictionary, matcha latte",
    "tech": "sleek consumer electronics on matte black desk, wireless charging pad, usb-c cable, case, soft product hero lighting",
    "gadget": "minimal tech flat lay, phone, earbuds case, charging cable, card holder, dark leather desk pad",
}


def _pick_visual_scene(topic: str) -> Optional[str]:
    t = topic.lower()
    # longest match first to avoid false positives
    for key in sorted(_TOPIC_VISUAL_KEYS.keys(), key=len, reverse=True):
        if key in t:
            return _TOPIC_VISUAL_KEYS[key]
    return None


def load_presets(path: Path = DEFAULT_PRESET_PATH) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@dataclass
class PromptBundle:
    prompt: str
    negative: str
    preset_name: str
    palette_locked: bool
    palette: List[str]


def build_prompt_for_card(
    *,
    topic: str,
    preset: Dict[str, Any],
    preset_name: str,
    card_index: int,   # 0 = cover, 1..N = inner cards
    card_count: int,
    keywords: Optional[Iterable[str]] = None,
    audience: str = "",
    emoji_mood: str = "",
    has_text: bool = False,
    exclude: Optional[Iterable[str]] = None,
    negative_base: List[str],
    extra_prompt_suffix: str = "",
) -> PromptBundle:
    """Compose a single card's (prompt, negative) from the preset schema + user fields.

    Pure function — no network, no filesystem.  Deterministic given inputs.
    """

    keywords = list(keywords or [])
    exclude = list(exclude or [])

    # 1. Palette lock line
    palette: List[str] = list(preset.get("palette", []))
    palette_lock = bool(preset.get("paletteLock", False))
    palette_line = ""
    if palette_lock and palette:
        joined = " ".join(palette)
        palette_line = f"palette strictly limited to hex colors {joined}, absolutely no other colors, strictly respect these 5 hex values"

    # 2. Topic → visually concrete scene line
    scene = _pick_visual_scene(topic) or ""
    topic_line = f"subject: {topic.strip()}. scene details: {scene}" if scene else f"subject: {topic.strip()}"

    # 3. Keywords → comma separated concrete objects line
    kw_line = f"key visual props: {', '.join(k.strip() for k in keywords)}" if keywords else ""

    # 4. Audience bias
    audience_line = ""
    if audience.strip():
        audience_line = f"demographic and styling aligned to: {audience.strip()}"

    # 5. Emoji / mood adjectives
    mood_line = ""
    if emoji_mood.strip():
        mood_line = f"emotional atmosphere adjectives: {emoji_mood.strip()}"

    # 6. Cover vs inner card role
    if card_index == 0:
        role = (
            "COVER IMAGE for social media feed: large hero visual, very eye-catching, "
            "strong focal point in center, clear hierarchy, stop-scrolling composition."
        )
    elif card_index == 1:
        role = (
            "INNER CARD step 1 / explanation: medium close-up detail shots, textures visible, "
            "clear visual markers, generous negative space for later overlay."
        )
    elif card_count >= 3 and card_index == card_count - 1:
        role = (
            "FINAL CARD / result shot: full overview picture, satisfying arrangement, "
            "open composition that works with a call-to-action overlay."
        )
    else:
        role = (
            f"INNER CARD {card_index} of a {card_count}-card carousel: "
            "educational comparison or step layout, balanced composition, readable margins, "
            "consistent look with previous cards (same palette, same lighting, same lens)."
        )

    # 7. Text-in-image handling — only dalle3 reliably renders Chinese text
    text_line = ""
    if has_text:
        text_line = (
            "clean legible typography inside composition block, serif font when editorial else rounded sans, "
            "readable but do not over-use text; if provider is not dalle3 this request is downgraded to no text."
        )
    else:
        text_line = "no text, no letters, no characters, no words anywhere in the image."

    # 8. Assemble the positive prompt, in order of strength (quality first -> rules -> visuals -> role -> suffix)
    parts: List[str] = []
    parts.extend(preset.get("qualityBooster", []))
    parts.extend(preset.get("composition", []))
    parts.extend(preset.get("lighting", []))
    parts.extend(preset.get("atmosphere", []))
    parts.append(preset.get("camera", ""))
    if palette_line:
        parts.append(palette_line)
    parts.append(topic_line)
    if kw_line:
        parts.append(kw_line)
    if audience_line:
        parts.append(audience_line)
    if mood_line:
        parts.append(mood_line)
    parts.append(role)
    parts.append(text_line)
    parts.append(
        "xiaohongshu style, pinterest aesthetic, viral social media hero visual, highly shareable composition."
    )
    if extra_prompt_suffix.strip():
        parts.append(extra_prompt_suffix.strip())

    prompt = ", ".join(seg for seg in (s.strip().rstrip(".") for s in parts if s and s.strip()) if seg)

    # 9. Negative
    negatives: List[str] = list(negative_base)
    negatives.extend(preset.get("negativeExtra", []))
    negatives.extend([e.strip() for e in exclude if e and e.strip()])
    # Deduplicate while preserving order
    seen = set()
    dedup: List[str] = []
    for n in negatives:
        if n and n not in seen:
            seen.add(n)
            dedup.append(n)
    negative = ", ".join(dedup)

    return PromptBundle(
        prompt=prompt,
        negative=negative,
        preset_name=preset_name,
        palette_locked=palette_lock,
        palette=palette,
    )


# ---------------------------------------------------------------------------
# Size / provider utilities
# ---------------------------------------------------------------------------

DEFAULT_PROVIDER_CHAIN = ["trae-native", "seedream-plugin", "dalle3", "fal-flux"]


def default_provider_chain() -> List[str]:
    return list(DEFAULT_PROVIDER_CHAIN)


def get_size_map(data: Dict[str, Any], ratio: str) -> Dict[str, Any]:
    size_map = data.get("sizeMap", {})
    if ratio not in size_map:
        raise KeyError(f"ratio '{ratio}' not in sizeMap; available: {sorted(size_map.keys())}")
    entry = dict(size_map[ratio])
    entry["ratio"] = ratio
    return entry


# ---------------------------------------------------------------------------
# Run directory + manifest
# ---------------------------------------------------------------------------

def new_run_id() -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    salt = hashlib.sha1(os.urandom(8)).hexdigest()[:6]
    return f"{ts}-{salt}"


# ---------------------------------------------------------------------------
# API-mode providers.  Each returns a tuple (ok: bool, image_path_or_reason)
# so the caller can treat them uniformly for the fallback loop.
# ---------------------------------------------------------------------------

@dataclass
class ProviderResult:
    ok: bool
    provider_id: str
    image_path: Optional[Path] = None
    reason: str = ""
    seed: Optional[int] = None
    attempts: int = 0
    latency_ms: int = 0


def _call_dalle3(bundle: PromptBundle, size_entry: Dict[str, Any], out_path: Path,
                 openai_api_key: str) -> ProviderResult:
    t0 = time.time()
    try:
        from openai import OpenAI  # type: ignore
    except Exception as exc:
        return ProviderResult(False, "dalle3", reason=f"openai package missing: {exc}", latency_ms=int((time.time()-t0)*1000))
    try:
        client = OpenAI(api_key=openai_api_key)
        # DALL·E 3 only supports a limited set of sizes; pick closest by pixels.
        w, h = int(size_entry["width"]), int(size_entry["height"])
        candidates = ["1024x1024", "1792x1024", "1024x1792"]
        def score(s: str) -> int:
            sw, sh = map(int, s.split("x"))
            return abs(sw - w) + abs(sh - h)
        chosen = min(candidates, key=score)
        response = client.images.generate(
            model="dall-e-3",
            prompt=bundle.prompt,
            size=chosen,
            quality="hd",
            n=1,
        )
        url = response.data[0].url
        if not url:
            return ProviderResult(False, "dalle3", reason="no url returned", latency_ms=int((time.time()-t0)*1000))
        # Download
        import urllib.request
        with urllib.request.urlopen(url, timeout=60) as resp:
            blob = resp.read()
        out_path.write_bytes(blob)
        seed = None  # DALL·E 3 does not return seed through public API today
        return ProviderResult(True, "dalle3", image_path=out_path, seed=seed,
                              latency_ms=int((time.time()-t0)*1000))
    except Exception as exc:
        return ProviderResult(False, "dalle3", reason=f"{type(exc).__name__}: {exc}",
                              latency_ms=int((time.time()-t0)*1000))


def _call_fal_flux(bundle: PromptBundle, size_entry: Dict[str, Any], out_path: Path,
                   fal_key: str) -> ProviderResult:
    t0 = time.time()
    try:
        import fal_client  # type: ignore
    except Exception as exc:
        return ProviderResult(False, "fal-flux", reason=f"fal-client package missing: {exc}",
                              latency_ms=int((time.time()-t0)*1000))
    try:
        os.environ["FAL_KEY"] = fal_key
        w, h = int(size_entry["width"]), int(size_entry["height"])
        # FAL image_size uses "WxH" string; bucket to a FLUX-friendly multiple of 32.
        def bucket(v: int) -> int:
            return max(512, min(1536, ((v + 15) // 32) * 32))
        image_size = f"{bucket(w)}x{bucket(h)}"
        handler = fal_client.submit(
            "fal-ai/flux-dev-lora",
            arguments={
                "prompt": bundle.prompt,
                "negative_prompt": bundle.negative,
                "image_size": image_size,
                "num_inference_steps": 32,
                "guidance_scale": 3.5,
                "num_images": 1,
                "enable_safety_checker": True,
            },
        )
        result = handler.get()
        images = result.get("images") or []
        if not images:
            return ProviderResult(False, "fal-flux", reason="no images returned",
                                  latency_ms=int((time.time()-t0)*1000))
        url = images[0].get("url")
        seed = result.get("seed")
        import urllib.request
        with urllib.request.urlopen(url, timeout=60) as resp:
            blob = resp.read()
        out_path.write_bytes(blob)
        return ProviderResult(True, "fal-flux", image_path=out_path, seed=seed,
                              latency_ms=int((time.time()-t0)*1000))
    except Exception as exc:
        return ProviderResult(False, "fal-flux", reason=f"{type(exc).__name__}: {exc}",
                              latency_ms=int((time.time()-t0)*1000))


def run_provider_chain(
    *,
    provider_ids: List[str],
    bundle: PromptBundle,
    size_entry: Dict[str, Any],
    out_path: Path,
    max_retries_per_provider: int = 3,
    dry_run: bool = False,
) -> ProviderResult:
    """Try each provider in order; for auth/rate-limit / missing skip to next;
       for network / corrupt images retry up to N with exponential backoff."""

    env = os.environ
    failures: List[Dict[str, Any]] = []

    for pid in provider_ids:
        if pid in ("trae-native", "seedream-plugin"):
            # These are not callable from inside a plain Python script — they
            # require the hosting agent's tool surface.  Record the task and
            # return ok=False with reason "agent-handoff-needed".  In
            # agent-mode the caller iterates via task.json instead.
            failures.append({"provider": pid, "reason": "requires agent tool surface, skipped in script API-mode"})
            continue

        if pid == "dalle3":
            key = env.get("OPENAI_API_KEY")
            if not key:
                failures.append({"provider": pid, "reason": "OPENAI_API_KEY missing"})
                continue
        elif pid == "fal-flux":
            key = env.get("FAL_KEY")
            if not key:
                failures.append({"provider": pid, "reason": "FAL_KEY missing"})
                continue
        else:
            failures.append({"provider": pid, "reason": f"unknown provider id '{pid}'"})
            continue

        for attempt in range(1, max_retries_per_provider + 1):
            if dry_run:
                return ProviderResult(False, pid, reason="dry-run: no real call")
            if pid == "dalle3":
                res = _call_dalle3(bundle, size_entry, out_path, key)
            else:  # fal-flux
                res = _call_fal_flux(bundle, size_entry, out_path, fal_key=env["FAL_KEY"])
            res.attempts = attempt
            if res.ok and out_path.exists():
                ok, why = validate_png(out_path)
                if not ok:
                    res.ok = False
                    res.reason = f"image validation failed: {why}"
                else:
                    ok2, why2 = validate_ratio(out_path, size_entry["ratio"])
                    if not ok2:
                        # Soft warn, don't hard reject unless strict mode.  We
                        # still mark ok but stash the reason in provider log.
                        res.reason = f"ratio warning: {why2}"
            if res.ok:
                return res
            failures.append({
                "provider": pid,
                "attempt": attempt,
                "reason": res.reason,
                "latency_ms": res.latency_ms,
            })
            # Retry backoff
            time.sleep(min(2 ** attempt, 10))

    return ProviderResult(False, provider_ids[-1] if provider_ids else "",
                          reason="all providers failed. log: " + json.dumps(failures, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Agent-mode helpers.  We write a tasks.json describing every image the host
# agent must produce, then wait for results to appear in an input/ folder,
# validating each before moving it into the run folder.
# ---------------------------------------------------------------------------

@dataclass
class CardTask:
    card_name: str           # "cover" | "card_1" | ...
    card_index: int
    ratio: str
    trae_size: str
    width: int
    height: int
    prompt: str
    negative: str
    preset: str


def _card_name(index: int) -> str:
    return "cover" if index == 0 else f"card_{index}"


def write_task_manifest(run_dir: Path, tasks: List[CardTask]) -> Path:
    payload = {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "task_mode": "agent-driven",
        "tasks": [asdict(t) for t in tasks],
    }
    p = run_dir / "tasks.json"
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_providers(raw: str) -> List[str]:
    if not raw or raw == "__default__":
        return default_provider_chain()
    return [p.strip() for p in raw.split(",") if p.strip()]


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="generate.py",
        description="yy-rednote-img: structured Xiaohongshu AI image pipeline",
    )
    ap.add_argument("--topic", required=True, help="Note topic, one sentence.")
    ap.add_argument("--cards", type=int, required=True, help="Total number of images including cover.")
    ap.add_argument("--style", required=True, help="Preset name in styles/presets.json.")
    ap.add_argument("--ratio", default="3:4", choices=["3:4", "1:1", "4:3", "9:16"])
    ap.add_argument("--keywords", default="", help="Comma separated visual keywords.")
    ap.add_argument("--audience", default="", help="Target demographic hint.")
    ap.add_argument("--mood", default="", help="Emoji/mood words, comma separated.")
    ap.add_argument("--exclude", default="", help="Extra negatives, comma separated.")
    ap.add_argument("--has-text", action="store_true", help="Request readable text in image.")
    ap.add_argument("--providers", default="__default__",
                    help="Provider chain comma separated (default: trae-native,seedream-plugin,dalle3,fal-flux).")
    ap.add_argument("--mode", choices=["agent", "api"], default="agent",
                    help="agent: write tasks.json for host agent; api: call OpenAI/FAL directly with keys.")
    ap.add_argument("--dry-run-prompts", action="store_true",
                    help="Only print prompts, never call any provider.")
    ap.add_argument("--strict", action="store_true",
                    help="Reject images where aspect ratio is off (tolerated by default).")
    ap.add_argument("--extra-prompt-suffix", default="",
                    help="Free-form text appended to every prompt (e.g. for brand consistency).")
    ap.add_argument("--output-dir", default=str(Path.cwd() / "output"),
                    help="Root directory for run outputs.")
    ap.add_argument("--resume", default="",
                    help="Existing run-id to continue (skips already valid & present outputs).")
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    try:
        presets_data = load_presets()
    except Exception as exc:
        print(f"[FATAL] cannot load presets: {exc}", file=sys.stderr)
        return 2

    if args.style not in presets_data["presets"]:
        print(f"[FATAL] style '{args.style}' not found. Available: {sorted(presets_data['presets'].keys())}",
              file=sys.stderr)
        return 2
    preset = presets_data["presets"][args.style]
    negative_base = presets_data["negativeBase"]
    size_entry = get_size_map(presets_data, args.ratio)

    provider_chain = _parse_providers(args.providers)

    # Run directory
    out_root = Path(args.output_dir).resolve()
    run_id = args.resume or new_run_id()
    run_dir = out_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    failed_dir = run_dir / "_failed"
    failed_dir.mkdir(exist_ok=True)

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    exclude = [k.strip() for k in args.exclude.split(",") if k.strip()]

    card_count = max(1, int(args.cards))
    tasks: List[CardTask] = []
    bundles: Dict[int, PromptBundle] = {}

    for idx in range(card_count):
        bundle = build_prompt_for_card(
            topic=args.topic,
            preset=preset,
            preset_name=args.style,
            card_index=idx,
            card_count=card_count,
            keywords=keywords,
            audience=args.audience,
            emoji_mood=args.mood,
            has_text=args.has_text,
            exclude=exclude,
            negative_base=negative_base,
            extra_prompt_suffix=args.extra_prompt_suffix,
        )
        bundles[idx] = bundle
        tasks.append(CardTask(
            card_name=_card_name(idx),
            card_index=idx,
            ratio=args.ratio,
            trae_size=size_entry["trae_size"],
            width=int(size_entry["width"]),
            height=int(size_entry["height"]),
            prompt=bundle.prompt,
            negative=bundle.negative,
            preset=args.style,
        ))

    # ----- dry-run: just print and exit -----
    if args.dry_run_prompts:
        print(json.dumps({
            "run_id": run_id,
            "style": args.style,
            "ratio": args.ratio,
            "size": size_entry,
            "provider_chain": provider_chain,
            "cards": [
                {
                    "name": t.card_name,
                    "index": t.card_index,
                    "trae_size": t.trae_size,
                    "prompt": bundles[t.card_index].prompt,
                    "negative": bundles[t.card_index].negative,
                }
                for t in tasks
            ],
        }, ensure_ascii=False, indent=2))
        return 0

    manifest: Dict[str, Any] = {
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "topic": args.topic,
        "style": args.style,
        "ratio": args.ratio,
        "size": size_entry,
        "provider_chain": provider_chain,
        "strict": args.strict,
        "cards": [],
    }

    # ----- agent-mode: write tasks.json, then try to validate any files already present -----
    if args.mode == "agent":
        tasks_path = write_task_manifest(run_dir, tasks)
        print(f"[agent-mode] Run dir: {run_dir}")
        print(f"[agent-mode] Tasks written to: {tasks_path}")
        print("[agent-mode] Now place generated images named as cover.png / card_1.png / ... into the run dir,")
        print("[agent-mode] or into a sibling 'input/' folder, then run with --resume to validate + finalize manifest.")

        # Try to finalize any images already present.
        any_missing = False
        for t in tasks:
            img_path = run_dir / f"{t.card_name}.png"
            if not img_path.exists():
                alt = run_dir / "input" / f"{t.card_name}.png"
                if alt.exists():
                    import shutil
                    shutil.move(str(alt), str(img_path))
            if not img_path.exists():
                any_missing = True
                manifest["cards"].append({
                    "name": t.card_name,
                    "index": t.card_index,
                    "status": "pending",
                    "prompt": t.prompt,
                    "negative": t.negative,
                    "preset": t.preset,
                    "trae_size": t.trae_size,
                })
                continue
            ok_png, why_png = validate_png(img_path)
            ok_rat, why_rat = validate_ratio(img_path, args.ratio)
            status_ok = ok_png and (ok_rat or not args.strict)
            if not status_ok:
                # Move to failed
                target = failed_dir / f"{t.card_name}.rejected.png"
                try:
                    import shutil
                    shutil.move(str(img_path), str(target))
                except OSError:
                    pass
            manifest["cards"].append({
                "name": t.card_name,
                "index": t.card_index,
                "status": "ok" if status_ok else "rejected",
                "size_bytes": img_path.stat().st_size if img_path.exists() else 0,
                "dims": get_image_size(img_path) if img_path.exists() else None,
                "png_valid": why_png,
                "ratio_valid": why_rat,
                "prompt": t.prompt,
                "negative": t.negative,
                "preset": t.preset,
                "trae_size": t.trae_size,
            })
        (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        if any_missing:
            print("[agent-mode] Some cards still missing image files.  Waiting for host agent to place them.")
            return 0
        print(f"[agent-mode] All cards validated. Manifest: {run_dir / 'manifest.json'}")
        return 0

    # ----- api-mode: iterate provider chain per card -----
    overall_ok = True
    for t in tasks:
        out_path = run_dir / f"{t.card_name}.png"
        if args.resume and out_path.exists():
            ok_png, _ = validate_png(out_path)
            if ok_png:
                manifest["cards"].append({
                    "name": t.card_name, "index": t.card_index, "status": "resumed",
                    "size_bytes": out_path.stat().st_size, "dims": get_image_size(out_path),
                })
                continue
        res = run_provider_chain(
            provider_ids=provider_chain,
            bundle=bundles[t.card_index],
            size_entry=size_entry,
            out_path=out_path,
            dry_run=False,
        )
        card_log = {
            "name": t.card_name,
            "index": t.card_index,
            "status": "ok" if res.ok else "failed",
            "provider_used": res.provider_id if res.ok else None,
            "result_reason": res.reason,
            "seed": res.seed,
            "latency_ms": res.latency_ms,
            "attempts": res.attempts,
            "prompt": t.prompt,
            "negative": t.negative,
            "preset": t.preset,
            "size_bytes": out_path.stat().st_size if out_path.exists() else 0,
            "dims": get_image_size(out_path) if out_path.exists() else None,
        }
        manifest["cards"].append(card_log)
        if not res.ok:
            overall_ok = False
        (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "run_dir": str(run_dir),
        "run_id": run_id,
        "success": overall_ok,
        "cards_succeeded": sum(1 for c in manifest["cards"] if c.get("status") in ("ok", "resumed")),
        "cards_total": len(manifest["cards"]),
    }, ensure_ascii=False, indent=2))
    return 0 if overall_ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n[interrupted]", file=sys.stderr)
        raise SystemExit(130)
    except Exception as _exc:
        traceback.print_exc()
        raise SystemExit(99)
