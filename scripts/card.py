"""把一段中文文案排成小红书可发的图文卡片（PNG）。

用法：
    python scripts/card.py --input content.json --out output/cards --theme ins-aesthetic

输入 content.json 的结构：
{
  "author": "@yourname",
  "cards": [
    {"type": "cover", "kicker": "封面", "title": "...", "subtitle": "..."},
    {"kicker": "01", "title": "...", "lead": "...", "bullets": ["...", "..."], "callout": "..."}
  ]
}

渲染方式：把卡片写成 HTML，调用本机 Chrome / Edge 无头模式按 1080×1440 截图。
中文由系统字体直接排版，不经过任何图像模型，所以不会出现错字或糊字。
"""

from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "card.html"
DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 1440

SANS = (
    '"Microsoft YaHei", "PingFang SC", "Noto Sans SC", '
    '"Source Han Sans SC", "Hiragino Sans GB", sans-serif'
)
SERIF = (
    '"Songti SC", "SimSun", "Noto Serif SC", '
    '"Source Han Serif SC", "STSong", serif'
)

# 卡片视觉主题，键名与 styles/presets.json 保持一致，方便同一套审美贯穿图片与卡片。
THEMES: dict[str, dict[str, str]] = {
    "ins-aesthetic": {
        "bg": "#FFF8F0", "fg": "#3A2E26", "accent": "#A67B5B",
        "muted": "#8C7A68", "panel": "#F1E4D4", "radius": "10px", "font": SANS,
    },
    "clean-minimal": {
        "bg": "#FFFFFF", "fg": "#141414", "accent": "#141414",
        "muted": "#767676", "panel": "#F2F2F2", "radius": "0px", "font": SANS,
    },
    "neo-chinese": {
        "bg": "#7C1017", "fg": "#F7EBD8", "accent": "#D9B04A",
        "muted": "#D9BFA2", "panel": "#8C1C22", "radius": "4px", "font": SERIF,
    },
    "y2k-funky": {
        "bg": "#F3E8FF", "fg": "#1B1033", "accent": "#FF2E88",
        "muted": "#6A5A86", "panel": "#E6D6FF", "radius": "22px", "font": SANS,
    },
    "magazine-editorial": {
        "bg": "#F3EFE7", "fg": "#171717", "accent": "#A63A2B",
        "muted": "#6E6A63", "panel": "#E7E1D5", "radius": "2px", "font": SERIF,
    },
    "emotional-daily": {
        "bg": "#F6E7CB", "fg": "#3B2A1C", "accent": "#C25E2C",
        "muted": "#80674E", "panel": "#EBD6B4", "radius": "12px", "font": SANS,
    },
    "product-flatlay": {
        "bg": "#EFEAE0", "fg": "#2E2A24", "accent": "#5F7350",
        "muted": "#77705F", "panel": "#E2DACC", "radius": "8px", "font": SANS,
    },
    "cute-illustration": {
        "bg": "#FFF4FA", "fg": "#43303C", "accent": "#FF7FA8",
        "muted": "#96808D", "panel": "#FCE3EF", "radius": "28px", "font": SANS,
    },
}

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
]


def find_browser() -> str | None:
    """按环境变量 → 常见安装路径 → PATH 的顺序找可用的浏览器可执行文件。"""
    env = os.environ.get("CHROME_PATH")
    if env and Path(env).exists():
        return env
    for path in CHROME_CANDIDATES:
        if Path(path).exists():
            return path
    local = os.environ.get("LOCALAPPDATA")
    if local:
        for name in ("chrome.exe", "msedge.exe"):
            p = Path(local) / "Google" / "Chrome" / "Application" / name
            if p.exists():
                return str(p)
    for name in ("google-chrome", "chromium", "chrome", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    return None


def title_size(text: str) -> int:
    """按标题实际宽度选字号，尽量一行放得下，不靠缩放或硬挤。"""
    available = 880
    text = text.strip()

    def width(size: int) -> float:
        total = 0.0
        for ch in text:
            # 中文按 1 个字宽估算，英文/数字按 0.55 估算，再加字间距。
            total += size * (0.55 if ord(ch) < 128 else 1.02) + 1
        return total

    for size in (100, 92, 84, 76, 68, 60, 54):
        if width(size) <= available:
            return size
    return 54


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _paragraphs(text: str) -> str:
    return "<br>".join(_esc(line) for line in text.strip().splitlines())


def build_body(card: dict[str, Any], index: int) -> str:
    """把一个 card 对象转成 HTML 主体。第一张默认按封面排版。"""
    title = _esc(card.get("title", ""))
    is_cover = card.get("type") == "cover" or index == 0

    if is_cover:
        subtitle = card.get("subtitle") or card.get("lead") or ""
        sub_html = f'<div class="subtitle">{_paragraphs(subtitle)}</div>' if subtitle else ""
        return (
            f'<div class="title">{title}</div>'
            f'<div class="rule"></div>'
            f"{sub_html}"
        )

    parts = [f'<div class="title">{title}</div>', '<div class="rule"></div>']
    lead = card.get("lead", "")
    if lead:
        parts.append(f'<div class="lead">{_paragraphs(lead)}</div>')

    bullets = card.get("bullets") or []
    if bullets:
        items = []
        for i, item in enumerate(bullets, 1):
            items.append(
                '<div class="bullet">'
                f'<div class="num">{i}</div>'
                f'<div class="bullet-text">{_esc(item)}</div>'
                "</div>"
            )
        parts.append(f'<div class="bullets">{"".join(items)}</div>')

    callout = card.get("callout", "")
    if callout:
        parts.append(f'<div class="callout">{_paragraphs(callout)}</div>')

    return "".join(parts)


def render_html(card: dict[str, Any], index: int, total: int,
                theme: dict[str, str], author: str) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    pager = f"{index + 1:02d} / {total:02d}"
    replacements = {
        "{{BG}}": theme["bg"],
        "{{FG}}": theme["fg"],
        "{{ACCENT}}": theme["accent"],
        "{{MUTED}}": theme["muted"],
        "{{PANEL}}": theme["panel"],
        "{{RADIUS}}": theme["radius"],
        "{{FONT}}": theme["font"],
        "{{TITLE_SIZE}}": str(title_size(card.get("title", ""))),
        "{{KICKER}}": _esc(card.get("kicker", "图文")),
        "{{BODY}}": build_body(card, index),
        "{{AUTHOR}}": _esc(author),
        "{{PAGER}}": _esc(pager),
    }
    for key, value in replacements.items():
        template = template.replace(key, value)
    return template


def screenshot(browser: str, page: Path, out: Path,
               width: int, height: int) -> None:
    """调用浏览器无头模式，把 HTML 精确截成 width×height。"""
    profile = Path(tempfile.mkdtemp(prefix="card-profile-"))
    cmd = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        f"--user-data-dir={profile}",
        "--force-device-scale-factor=1",
        f"--window-size={width},{height}",
        f"--screenshot={out}",
        page.as_uri(),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=90, errors="replace")
    finally:
        shutil.rmtree(profile, ignore_errors=True)

    if not out.exists():
        detail = (proc.stderr or proc.stdout or "").strip()[:400]
        raise RuntimeError(f"浏览器没有产出截图：{detail}")


def check_png(path: Path, width: int, height: int) -> tuple[int, int]:
    """校验 PNG 文件头与真实宽高，避免把截断文件当成成品。"""
    raw = path.read_bytes()
    if len(raw) < 24 or raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path.name} 不是有效的 PNG")
    w, h = struct.unpack(">II", raw[16:24])
    if (w, h) != (width, height):
        raise ValueError(f"{path.name} 尺寸为 {w}×{h}，期望 {width}×{height}")
    return w, h


def load_content(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cards = data.get("cards")
    if not isinstance(cards, list) or not cards:
        raise ValueError("content.json 里必须有非空的 cards 数组")
    for i, card in enumerate(cards):
        if not isinstance(card, dict) or not str(card.get("title", "")).strip():
            raise ValueError(f"第 {i + 1} 张卡片缺少 title")
    return data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="中文文案 → 小红书图文卡片")
    ap.add_argument("--input", required=True, help="内容 JSON 路径")
    ap.add_argument("--out", required=True, help="输出目录")
    ap.add_argument("--theme", default="ins-aesthetic", choices=sorted(THEMES))
    ap.add_argument("--author", default="", help="底部署名，默认取 JSON 里的 author")
    ap.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    ap.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    args = ap.parse_args(argv)

    try:
        content = load_content(Path(args.input))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    browser = find_browser()
    if not browser:
        print("[ERROR] 没找到 Chrome 或 Edge。装一个，或设置 CHROME_PATH 指向可执行文件。",
              file=sys.stderr)
        return 3

    theme = THEMES[args.theme]
    author = args.author or content.get("author", "")
    cards = content["cards"]
    total = len(cards)

    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir = out_dir / "_html"
    work_dir.mkdir(exist_ok=True)

    produced: list[Path] = []
    for i, card in enumerate(cards):
        name = "cover.png" if i == 0 else f"card_{i}.png"
        page = work_dir / f"{name[:-4]}.html"
        page.write_text(render_html(card, i, total, theme, author), encoding="utf-8")
        target = out_dir / name
        try:
            screenshot(browser, page, target, args.width, args.height)
            check_png(target, args.width, args.height)
        except (RuntimeError, ValueError) as exc:
            print(f"[ERROR] 第 {i + 1} 张：{exc}", file=sys.stderr)
            return 4
        produced.append(target)
        print(f"[OK] {target}")

    print(f"[DONE] {len(produced)} 张卡片 → {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
