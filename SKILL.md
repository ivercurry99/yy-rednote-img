---
name: yy-text2-xhs-img
description: "Structured Prompt + multi-model adapter for creating Xiaohongshu (Little Red Book) cover & card images via AI text-to-image. Invoke when user needs stable, style-consistent XHS imagery; supports TRAE built-in, Seedream plugin, DALL·E 3, and FLUX with automatic fallback. 8 built-in XHS presets + negative library."
license: MIT
version: 1.0.0
author: YYIver
triggers:
  - "小红书生图"
  - "xhs 配图"
  - "text2 xhs img"
  - "小红书 AI 封面"
  - "生成小红书图片"
  - "yy text2 xhs"
---

# yy-text2-xhs-img · Xiaohongshu AI Image Generator

Turn a one-line brief into a *consistent*, *reproducible*, *degradable* pipeline of Xiaohongshu-ready images. Instead of rolling the dice each time, we:
1. **lock the Prompt** with a structured schema + 8 preset style JSONs;
2. **dispatch across 4 providers** with automatic fallback (TRAE native → Seedream plugin → DALL·E 3 → FLUX);
3. **validate every output** (PNG header, size, ratio) + retry up to 3x;
4. **write a manifest.json** so any run can be reproduced exactly.

> This skill focuses on **AI text-to-image**. For HTML-template card rendering, use `xhs-note-creator`.

---

## Core features

| Pain | Fix in this skill |
|---|---|
| Colors / camera drift between images | **8 preset JSON files** lock palette, composition, lighting, atmosphere, camera. |
| A single model being rate-limited breaks everything | **4-provider fallback chain**. Any one works → you get images. |
| Missing negative prompts → watermarks / 6 fingers | **XHS negative library** (30+ terms) auto-appended every time. |
| Wrong aspect ratio for XHS feed | **Ratio map** locked to 3:4 / 1:1 / 4:3 / 9:16 per model's native size. |
| Generated file is corrupt / empty | **Integrity check**: PNG magic + >=50KB + ratio within 1% tolerance; retry on fail. |
| Cannot reproduce a good result | **manifest.json** records model + seed + prompt + preset per image. |

---

## Standard 5-step workflow

### Step 1 — Collect requirements (structured fields)

Don't write a long sentence. First split the user's intent into fields.

| Field | Required | Meaning | Example |
|---|---|---|---|
| `topic` | Yes | What the note is about, audience + subject. | "Summer oily skincare 3 steps for 20s women" |
| `card_count` | Yes | Total images including cover. Usually `4` (1 cover + 3 inner). | `4` |
| `style_preset` | Yes | One of 8 presets (see next section). | `ins-aesthetic` |
| `ratio` | Yes | `3:4` / `1:1` / `4:3` / `9:16`. 3:4 is XHS feed default. | `3:4` |
| `emoji_mood` | No | Mood keywords (translated to atmosphere adjectives). | "fresh, creamy, healing" |
| `keywords` | No | Visual / SEO keywords → concrete objects & textures. | "sun cream, texture smear, close-up dropper" |
| `audience` | No | Target demo, used to bias skin / wardrobe / age. | "east-asian women 20-30" |
| `has_text` | No | Put readable text in image? **Default false** (most models mangle Chinese). Switch to dalle3 when true. | `false` |
| `reference_style` | No | Free-text extra style hint. | "Japanese magazine vivi aesthetic" |
| `exclude` | No | Extra negative terms appended. | "no face, no model" |

If user doesn't specify optional fields, pick sensible defaults and tell them what you assumed at the end. Do not loop-ask.

### Step 2 — Pick a style preset (8 built-in)

| preset | Visual look | Best for |
|---|---|---|
| `ins-aesthetic` | Cream whites, soft window light, low contrast, 20%+ negative space | skincare / fashion / lifestyle |
| `clean-minimal` | Pure white seamless, top-down flat, product centered, hard contact shadow | cosmetics / e-commerce / single-product hero |
| `neo-chinese` | Cinnabar red + 24k gold palette, ink texture, guochao motifs | festival / tea / cultural goods / lipstick |
| `y2k-funky` | Hyper-saturated, chrome + magenta + cyan, flash-photo, 2000s vibe | campus / gen-z / trend / summer |
| `magazine-editorial` | Vogue editorial, 35mm Portra grain, rule-of-thirds, copy space left | long-form article / opinion / high-fashion |
| `emotional-daily` | Golden-hour warm, handheld candid, Kodak Gold 200 grain, cozy | food diary / cafe hopping / travel / mood |
| `product-flatlay` | True 90° top-down, linen/kraft background, props arranged sparingly | haul / unboxing / collection / routine steps |
| `cute-illustration` | Flat vector + thick rounded outline + Sanrio pastel macaron palette | knowledge cards / tutorial / kids education |

> Presets live in `styles/presets.json`. You can add your own by following the same schema.

### Step 3 — Run the generator

```bash
# Default & recommended (no API key needed; uses TRAE built-in first)
python scripts/generate.py \
  --topic "Summer oily skincare 3-step routine" \
  --cards 4 \
  --style ins-aesthetic \
  --ratio 3:4

# Explicit provider chain (each auto-falls to the next on failure)
python scripts/generate.py \
  --topic "Qixi festival guochao lipstick haul" \
  --cards 5 \
  --style neo-chinese \
  --ratio 3:4 \
  --providers trae-native,seedream-plugin,dalle3

# For real DALL·E 3 / FAL FLUX, export keys (see references/fallback-strategy.md)
# export OPENAI_API_KEY=sk-xxx
# export FAL_KEY=xxxx:xxxx

# Validate prompt without spending credits (just print, no API calls)
python scripts/generate.py \
  --topic "dry run first" --cards 1 --style magazine-editorial --ratio 3:4 \
  --dry-run-prompts
```

**Output layout** (each run gets its own timestamped dir):
```
output/20260829-200215-abc123/
├── cover.png
├── card_1.png  card_2.png  card_3.png
├── manifest.json      ← model / seed / prompt / preset log
└── _failed/           ← corrupt images discarded in retries
```

### Step 4 — Auto QA (always runs)

After generation, the script enforces (fails → retries the card):

- [x] File exists AND size >= 50 KB
- [x] PNG header `\x89PNG` matches (reject truncated / corrupt)
- [x] Count matches `--cards`
- [x] Aspect ratio error < 1% (read back W/H with Pillow)

3 consecutive failures of the same provider → switch to the next one in the chain.

### Step 5 — Deliver + preserve manifest

Always tell the user:
1. How many images were produced, and where the run dir is.
2. Which preset + which provider actually succeeded (so they can repeat the same combo next time).
3. Where `manifest.json` lives if they want reproducibility.

---

## Provider adapter overview

Full guide: `references/fallback-strategy.md` and `references/model-matrix.md`.

| Provider ID | What it needs | Pros | When to pick |
|---|---|---|---|
| `trae-native` | Host exposes `GenerateImage` tool | **Zero-config, free.** Default first pick. | Default #1 |
| `seedream-plugin` | TRAE Seedream plugin authorized | Cinematic color, Chinese friendly, fast. | TRAE environments |
| `dalle3` | `OPENAI_API_KEY` env var | Only one that draws readable Chinese text. | When `has_text=true` |
| `fal-flux` | `FAL_KEY` env var | Richest detail, best human anatomy, strongest style lock. | High-quality marketing / style-heavy |

**Default fallback order** (overridable with `--providers`):
`trae-native → seedream-plugin → dalle3 → fal-flux`

---

## Repository layout

```
yy-text2-xhs-img/
├── SKILL.md                    # Agent behaviour spec (this file)
├── README.md                   # Human-facing GitHub README
├── LICENSE                     # MIT
├── requirements.txt            # Optional Python deps (Pillow + optional APIs)
├── styles/
│   └── presets.json            # 8 style presets + negativeBase + sizeMap
├── scripts/
│   └── generate.py             # Main script: schema -> prompt -> providers -> validate -> manifest
├── references/
│   ├── prompt-engineering.md   # XHS prompt engineering playbook
│   ├── model-matrix.md         # Which model for which scenario
│   └── fallback-strategy.md    # Fallback chain + how to configure API keys
├── tests/
│   └── test_generate.py        # Unit tests (prompt build, size map, retry logic) — mock all real calls
├── evals/
│   └── evals.json              # Regression eval cases
└── .github/workflows/ci.yml    # CI: pytest + presets.json validation + syntax check
```

---

## Trigger phrases (for agent matching)

- "小红书生图", "小红书配图", "xhs 配图"
- "生成小红书封面", "小红书 AI 封面"
- "text2 xhs img", "yy text2 xhs"
- "帮我画 4 张小红书护肤图" / any "xiaohongshu + images" combination intent
