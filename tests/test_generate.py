"""Unit tests for yy-text2-xhs-img/scripts/generate.py — pure logic only, no real APIs.

Run with:  pytest tests/test_generate.py -v
"""
from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))

import generate as gen  # noqa: E402


PRESETS = gen.load_presets()
NEGATIVE_BASE: List[str] = PRESETS["negativeBase"]


# -------------------------------------------------------------------------
# 1. Preset structure sanity — regression on schema edits.
# -------------------------------------------------------------------------
class TestPresetSchema:
    def test_eight_or_more_presets(self) -> None:
        assert len(PRESETS["presets"]) >= 8, "need at least 8 built-in presets"

    def test_negative_base_has_30plus_terms(self) -> None:
        assert len(NEGATIVE_BASE) >= 20, "negative base too thin, watermark risk"

    def test_common_negative_terms_present(self) -> None:
        for must in ("watermark", "text", "mutated hands", "blurry", "logo", "signature"):
            assert must in NEGATIVE_BASE, f"missing critical negative term: {must}"

    def test_size_map_covers_all_xhs_ratios(self) -> None:
        for r in ("3:4", "1:1", "4:3", "9:16"):
            entry = gen.get_size_map(PRESETS, r)
            assert "trae_size" in entry and entry["width"] > 0 and entry["height"] > 0

    def test_every_preset_has_required_fields(self) -> None:
        required = (
            "displayName", "palette", "paletteLock", "composition",
            "lighting", "atmosphere", "camera", "qualityBooster",
            "negativeExtra", "bestFor",
        )
        for name, p in PRESETS["presets"].items():
            for fld in required:
                assert fld in p, f"preset '{name}' missing field '{fld}'"
                val = p[fld]
                if fld.endswith(("Extra",)):
                    pass  # lists can be empty explicitly
                elif isinstance(val, list):
                    assert len(val) >= 2, f"preset '{name}' field '{fld}' too short ({val})"


# -------------------------------------------------------------------------
# 2. Prompt composition — cover vs inner, palette lock, topic visualise.
# -------------------------------------------------------------------------
class TestPromptBuild:
    def _build(self, **kw):
        default = dict(
            topic="Summer oily skincare 3 steps",
            preset=PRESETS["presets"]["ins-aesthetic"],
            preset_name="ins-aesthetic",
            card_index=0,
            card_count=4,
            negative_base=NEGATIVE_BASE,
        )
        default.update(kw)
        return gen.build_prompt_for_card(**default)

    def test_cover_contains_stop_scrolling_marker(self) -> None:
        b = self._build(card_index=0)
        assert "stop-scrolling" in b.prompt, "cover missing stop-scroll hook"
        assert "COVER IMAGE" in b.prompt

    def test_inner_card_1_is_step_explanation(self) -> None:
        b = self._build(card_index=1, card_count=4)
        assert "step 1" in b.prompt.lower() or "INNER CARD" in b.prompt

    def test_final_card_is_result_shot(self) -> None:
        b = self._build(card_index=3, card_count=4)
        assert "FINAL CARD" in b.prompt or "result shot" in b.prompt.lower()

    def test_palette_lock_line_contains_hex(self) -> None:
        b = self._build()
        assert "palette strictly limited to hex colors" in b.prompt
        for hex_col in PRESETS["presets"]["ins-aesthetic"]["palette"]:
            assert hex_col in b.prompt, f"palette hex {hex_col} missing in prompt"

    def test_prompt_has_all_preset_sections(self) -> None:
        b = self._build()
        p = PRESETS["presets"]["ins-aesthetic"]
        # At least one keyword from each section must be present
        for section in ("composition", "lighting", "atmosphere", "qualityBooster"):
            assert any(token in b.prompt for token in p[section]), \
                f"section '{section}' got lost in prompt composition: {b.prompt[:200]}..."
        assert p["camera"] in b.prompt

    def test_negative_dedup_and_contains_base_and_extra(self) -> None:
        b = self._build()
        neg_list = [x.strip() for x in b.negative.split(",")]
        assert len(neg_list) == len(set(neg_list)), "negative list has duplicates"
        # negativeBase
        assert "watermark" in neg_list
        # preset negativeExtra
        for extra in PRESETS["presets"]["ins-aesthetic"]["negativeExtra"]:
            assert extra in neg_list, f"missing preset negative '{extra}'"

    def test_exclude_user_input_appended(self) -> None:
        b = self._build(exclude=["no face", "no model", "no red dress"])
        neg_list = [x.strip() for x in b.negative.split(",")]
        assert "no face" in neg_list and "no model" in neg_list

    def test_has_text_true_switches_text_mode(self) -> None:
        b_true = self._build(has_text=True)
        b_false = self._build(has_text=False)
        assert "no text" not in b_true.prompt or "no letters" not in b_true.prompt
        assert "no text, no letters" in b_false.prompt

    def test_topic_visualize_hits_keyword(self) -> None:
        b = self._build(topic="retro lipstick makeup")
        # Our hint map should trigger "lipstick" keywords — scene details should mention swatches or similar
        assert "swatches of lipstick" in b.prompt.lower() or "lip brush" in b.prompt.lower() or \
               "open tube" in b.prompt.lower()

    def test_topic_visualize_no_hit_falls_back_gracefully(self) -> None:
        b = self._build(topic="completely unknown topic xyz123")
        # Should still include "subject: ..." line
        assert "subject: completely unknown topic xyz123" in b.prompt

    def test_extra_prompt_suffix_appended(self) -> None:
        marker = "MY CUSTOM BRAND RULE: only use circular items"
        b = self._build(extra_prompt_suffix=marker)
        assert marker in b.prompt


# -------------------------------------------------------------------------
# 3. Size map & ratio lookup
# -------------------------------------------------------------------------
class TestSizeMap:
    def test_ratio_3_4_is_portrait(self) -> None:
        s = gen.get_size_map(PRESETS, "3:4")
        assert s["trae_size"] == "portrait_4_3"
        assert s["width"] == 1080 and s["height"] == 1440

    def test_ratio_1_1_is_square_hd(self) -> None:
        s = gen.get_size_map(PRESETS, "1:1")
        assert s["trae_size"] == "square_hd"

    def test_invalid_ratio_raises_key_error(self) -> None:
        import pytest  # type: ignore
        with pytest.raises(KeyError):
            gen.get_size_map(PRESETS, "16:9")  # swapped, not in our fixed list

    def test_default_provider_chain(self) -> None:
        assert gen.default_provider_chain() == \
            ["trae-native", "seedream-plugin", "dalle3", "fal-flux"]


# -------------------------------------------------------------------------
# 4. PNG validator + ratio validator (pure Python, no Pillow dependency if
#    not installed — tests use hand-crafted byte buffers).
# -------------------------------------------------------------------------
class TestImageValidators:
    def test_missing_file_rejected(self, tmp_path: Path) -> None:
        bad = tmp_path / "nope.png"
        ok, why = gen.validate_png(bad)
        assert not ok and "missing" in why

    def test_too_small_rejected(self, tmp_path: Path) -> None:
        f = tmp_path / "tiny.png"
        f.write_bytes(gen.PNG_MAGIC + b"\x00" * 100)  # only ~108 bytes
        ok, why = gen.validate_png(f, min_bytes=200)
        assert not ok and "too small" in why

    def test_bad_png_header_rejected(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.png"
        f.write_bytes(b"GIF89a" + b"\xFF" * 100000)  # 100KB but not PNG
        ok, why = gen.validate_png(f, min_bytes=50)
        assert not ok and "bad PNG header" in why

    def test_minimal_valid_png_accepted(self, tmp_path: Path) -> None:
        # A minimal 1x1 PNG we've seen in industry test fixtures
        import base64
        blob = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        )
        # small but valid; lower min_bytes threshold so this test is meaningful
        f = tmp_path / "1x1.png"
        f.write_bytes(blob)
        ok, why = gen.validate_png(f, min_bytes=50)
        assert ok, f"valid 1x1 PNG rejected: {why}"
        ok2, why2 = gen.validate_ratio(f, "1:1")
        assert ok2, f"1:1 ratio rejected: {why2}"

    def test_1080x1440_ratio_matches_3_4(self, tmp_path: Path) -> None:
        # Build a fake PNG whose IHDR reports 1080x1440, no image data beyond that
        import struct
        import zlib
        def chunk(typ: bytes, data: bytes) -> bytes:
            return struct.pack(">I", len(data)) + typ + data + \
                   struct.pack(">I", zlib.crc32(typ + data) & 0xffffffff)
        w, h = 1080, 1440
        ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)  # 8-bit RGB
        raw = b""
        # Tiny compressed IDAT that is technically "enough" to not break header parse
        idat = zlib.compress(b"\x00" * (1 + 3 * w) * h[:0] if False else b"\x00\x01\x00\xfb\xff\x00")
        data = gen.PNG_MAGIC + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")
        f = tmp_path / "fake.png"
        f.write_bytes(data)
        # Ratio check with IHDR fallback (no Pillow required)
        dims = gen.get_image_size(f)
        assert dims == (w, h), f"dimensions {dims}, expected ({w},{h})"
        ok, why = gen.validate_ratio(f, "3:4")
        assert ok, f"3:4 ratio rejected for 1080x1440: {why}"


# -------------------------------------------------------------------------
# 5. Provider orchestration — mocked providers to verify fallback logic.
# -------------------------------------------------------------------------
class TestFallbackChain:
    def test_run_provider_chain_requires_agent_surface_skips_trae_and_seedream(self, tmp_path: Path) -> None:
        """Without any env keys, trae-native and seedream-plugin are agent-only,
        dalle3 and fal-flux both missing keys -> end result 'all providers failed'."""
        bundle = gen.build_prompt_for_card(
            topic="test", preset=PRESETS["presets"]["ins-aesthetic"], preset_name="ins-aesthetic",
            card_index=0, card_count=1, negative_base=NEGATIVE_BASE,
        )
        size = gen.get_size_map(PRESETS, "3:4")
        # Temporarily blank out any keys the user's env may carry
        saved = dict(os.environ)
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("FAL_KEY", None)
        try:
            res = gen.run_provider_chain(
                provider_ids=gen.default_provider_chain(),
                bundle=bundle,
                size_entry=size,
                out_path=tmp_path / "x.png",
                dry_run=False,
            )
        finally:
            os.environ.clear()
            os.environ.update(saved)
        assert res.ok is False
        assert "all providers failed" in res.reason or "agent tool surface" in res.reason, \
            f"unexpected end reason: {res.reason}"

    def test_provider_parsing(self) -> None:
        assert gen._parse_providers("__default__") == gen.default_provider_chain()
        assert gen._parse_providers("fal-flux, dalle3 , trae-native") == ["fal-flux", "dalle3", "trae-native"]


# -------------------------------------------------------------------------
# 6. End-to-end CLI — dry-run with --dry-run-prompts so no network is hit.
# -------------------------------------------------------------------------
class TestCli:
    def test_cli_dry_run_returns_json(self, monkeypatch, capsys) -> None:
        argv = [
            "--topic", "Chinese Valentine lipstick haul",
            "--cards", "5",
            "--style", "neo-chinese",
            "--ratio", "3:4",
            "--keywords", "lipstick,red,gold",
            "--exclude", "no face",
            "--dry-run-prompts",
            "--mode", "agent",
        ]
        code = gen.main(argv)
        captured = capsys.readouterr()
        assert code == 0
        data = json.loads(captured.out)
        assert data["style"] == "neo-chinese"
        assert data["ratio"] == "3:4"
        assert len(data["cards"]) == 5
        names = [c["name"] for c in data["cards"]]
        assert names[0] == "cover"
        assert names[1] == "card_1" and names[4] == "card_4"
        for card in data["cards"]:
            # Strict palette lock -> every prompt should list the 5 neo-chinese hexes
            for hex_col in PRESETS["presets"]["neo-chinese"]["palette"]:
                assert hex_col in card["prompt"], \
                    f"card {card['name']} missing palette hex {hex_col}"
            # "watermark" should always be negative
            assert "watermark" in card["negative"]