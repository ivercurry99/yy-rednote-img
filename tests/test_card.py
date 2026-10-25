"""文字卡片渲染的纯逻辑测试，不依赖浏览器。

Run with:  pytest tests/test_card.py -v
"""
from __future__ import annotations

import json
import struct
import sys
import zlib
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))

import card  # noqa: E402


class TestTitleSize:
    def test_short_title_uses_largest_size(self) -> None:
        assert card.title_size("复利") == 100

    def test_longer_title_falls_back_to_smaller_size(self) -> None:
        assert card.title_size("3 个让早起变简单的方法") < 100

    def test_very_long_title_still_returns_usable_size(self) -> None:
        size = card.title_size("这是一段非常非常长的标题用来测试字号自动回退的下限")
        assert size == 54

    def test_estimated_width_never_exceeds_available(self) -> None:
        text = "新手记账第一周怎么开始"
        size = card.title_size(text)
        estimated = sum(size * (0.55 if ord(ch) < 128 else 1.02) + 1 for ch in text)
        assert estimated <= 880


class TestBuildBody:
    def test_first_card_renders_as_cover(self) -> None:
        body = card.build_body({"title": "封面标题", "subtitle": "副标题"}, 0)
        assert 'class="title"' in body
        assert "subtitle" in body
        assert "bullets" not in body

    def test_bullets_are_numbered_in_order(self) -> None:
        body = card.build_body(
            {"title": "标题", "bullets": ["第一条", "第二条"]}, 1
        )
        assert body.count('class="num"') == 2
        assert "第一条" in body and "第二条" in body

    def test_callout_rendered_when_present(self) -> None:
        body = card.build_body({"title": "标题", "callout": "一句金句"}, 1)
        assert "一句金句" in body and "callout" in body

    def test_html_is_escaped(self) -> None:
        body = card.build_body({"title": "<script>alert(1)</script>"}, 0)
        assert "<script>" not in body
        assert "&lt;script&gt;" in body

    def test_multiline_lead_becomes_line_breaks(self) -> None:
        body = card.build_body({"title": "标题", "lead": "第一行\n第二行"}, 1)
        assert "第一行<br>第二行" in body


class TestRenderHtml:
    def test_all_placeholders_replaced(self) -> None:
        page = card.render_html(
            {"title": "测试标题", "kicker": "标签"},
            1,
            4,
            card.THEMES["ins-aesthetic"],
            "@yy",
        )
        assert "{{" not in page
        assert "测试标题" in page
        assert "02 / 04" in page
        assert "#FFF8F0" in page

    def test_every_theme_renders(self) -> None:
        for name, theme in card.THEMES.items():
            page = card.render_html({"title": f"{name} 标题"}, 0, 1, theme, "@yy")
            assert theme["bg"] in page
            assert theme["accent"] in page


class TestLoadContent:
    def test_rejects_empty_cards(self, tmp_path: Path) -> None:
        p = tmp_path / "c.json"
        p.write_text(json.dumps({"cards": []}), encoding="utf-8")
        with pytest.raises(ValueError):
            card.load_content(p)

    def test_rejects_card_without_title(self, tmp_path: Path) -> None:
        p = tmp_path / "c.json"
        p.write_text(json.dumps({"cards": [{"lead": "无标题"}]}), encoding="utf-8")
        with pytest.raises(ValueError):
            card.load_content(p)

    def test_accepts_valid_content(self, tmp_path: Path) -> None:
        p = tmp_path / "c.json"
        p.write_text(
            json.dumps({"author": "@yy", "cards": [{"title": "标题"}]}),
            encoding="utf-8",
        )
        assert card.load_content(p)["author"] == "@yy"


def _png_bytes(width: int, height: int) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    chunk = b"IHDR" + ihdr
    body = struct.pack(">I", len(ihdr)) + chunk + struct.pack(">I", zlib.crc32(chunk))
    return b"\x89PNG\r\n\x1a\n" + body


class TestCheckPng:
    def test_accepts_matching_size(self, tmp_path: Path) -> None:
        p = tmp_path / "ok.png"
        p.write_bytes(_png_bytes(1080, 1440))
        assert card.check_png(p, 1080, 1440) == (1080, 1440)

    def test_rejects_wrong_size(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.png"
        p.write_bytes(_png_bytes(800, 800))
        with pytest.raises(ValueError):
            card.check_png(p, 1080, 1440)

    def test_rejects_non_png(self, tmp_path: Path) -> None:
        p = tmp_path / "x.png"
        p.write_bytes(b"not a png file at all")
        with pytest.raises(ValueError):
            card.check_png(p, 1080, 1440)
