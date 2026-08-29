<p align="center">
  <strong><samp>yy-text2-xhs-img</samp></strong><br>
  <sub>Structured Prompt × Multi-Provider Adapter for Xiaohongshu AI Images</sub>
</p>

<p align="center">
  <a href="#what-it-does"><kbd>What it does</kbd></a>
  <a href="#why-not-just-roll-a-prompt"><kbd>Why stable</kbd></a>
  <a href="#8-presets"><kbd>8 presets</kbd></a>
  <a href="#installation"><kbd>Install</kbd></a>
  <a href="#quick-start"><kbd>Quick start</kbd></a>
  <a href="#roadmap--contributing"><kbd>Contributing</kbd></a>
  <a href="#license"><kbd>License</kbd></a>
</p>

---

## What it does

`yy-text2-xhs-img` turns a **one-line brief** (e.g. *"4 Xiaohongshu cards for a
summer oily-skincare 3-step routine"*) into a **consistent, reproducible,
degradable** set of AI images.  Instead of "rolling a prompt" and hoping for
the best each time, we lock everything down with schemas before any model is
called.

The core script `scripts/generate.py` handles three hard things:

| Problem | Solution in this repo |
|---|---|
| 🎨 Style / colours drift between cards | **Styles preset JSON** — 8 Xiaohongshu-tested look books with palette (5 hex, locked), composition, lighting, atmosphere, camera & anti-style negative extras. |
| ⛔ Watermarks / bad anatomy / text garbage | **Universal negative base (30+ terms)** + preset anti-extra + user exclude layered **every** call. |
| 🚦 One provider dies → the whole post is stuck | **4-provider fallback chain**: TRAE native → Seedream plugin → DALL·E 3 → FLUX.  3 retries + exponential backoff per provider, failover to next. |
| 📏 Wrong aspect ratio for the XHS feed | **Fixed sizeMap** for 3:4 / 1:1 / 4:3 / 9:16 mapped to each provider's closest native bucket. |
| 🚫 Corrupt / truncated outputs silently shipped | **PNG magic + 50 KB minimum + aspect ratio tolerance < 1 %** check per image; failures are auto-retried, rejected files moved to `_failed/`. |
| 🔁 "That post from last week looked better, can we repeat it?" | **manifest.json** records provider id, seed, prompt, preset & dimensions per card — re-run verbatim. |

Two run modes so you can use the same logic whether you're in an Agent host
(TRAE / Codex / Claude Desktop skills folder) or calling APIs from a shell:

- **Agent mode** (default): writes `tasks.json` describing every card; the
  host agent calls its built-in `GenerateImage` / Seedream plugin / etc. and
  drops PNGs into the run dir; second pass validates + writes manifest.
- **API mode** (`--mode api`): script calls OpenAI DALL·E 3 / FAL FLUX
  directly if keys are present in environment variables.

---

## Why not just "roll a prompt" every time?

Because consistency is *the* product feature on Xiaohongshu.  Your reader
scans a 4-image carousel; if card 1 is creamy INS and card 2 is Y2K chrome
they swipe away before the CTA.  The script fixes this by enforcing a
strict **order of prompt composition** (fidelity → layout → light → atmosphere →
palette lock → visualized scene → role), *then* appending the role-specific
hook for cover / step-1 / middle / final-shot.

Even so, you can still freely customise via:

```
--keywords "prop1, prop2, texture3"
--audience "east-asian women 20-28"
--mood "healing, soft, pastel cream"
--exclude "no face, no hands"
--extra-prompt-suffix "brand consistency rule: circular accents, gold foil linework"
```

Everything is deterministic, pure functions under test, no random number
generator seeded inside the library by accident.

---

## 8 presets

Each preset is a fully-tuned, locked, Xiaohongshu-native look book with
**5 hex palette**, **4+ composition rules**, **4+ lighting rules**,
**atmosphere + camera + qualityBooster + anti negativeExtra**:

| `--style` | Visual | Best for |
|---|---|---|
| `ins-aesthetic` | Cream whites, soft 50 mm window light, low contrast, gentle negative space | Skincare · fashion flat lays · lifestyle |
| `clean-minimal` | 100 % seamless white, top-down symmetrical, hard contact shadow | Single product hero · cosmetics · catalog |
| `neo-chinese` | Cinnabar red + 24 K gold palette, ink-wash overlay, guochao motifs | Festivals · tea · lipstick · cultural goods |
| `y2k-funky` | Magenta/cyan chrome, flash-photo washed, pearlescent glossy | Gen-Z · campus · trend · summer topics |
| `magazine-editorial` | Portra 400 grain, editorial three-light setup, rule-of-thirds, copy-safe 30 % | Long-form · opinion pieces · high-fashion |
| `emotional-daily` | Golden-hour warm tint, 35 mm candid, heavy film grain, slice-of-life | Food diaries · cafe · travel moods |
| `product-flatlay` | True 90° flat-lay, linen/kraft paper, matching props, balanced haul layout | Collections · hauls · routine steps · unboxing |
| `cute-illustration` | Thick rounded outlines, Sanrio-pastel macaron palette, flat vector | Knowledge cards · tutorials · kids education |

See `styles/presets.json` for the full schema and
`references/prompt-engineering.md` § 7 for the exact spec to add your own.

---

## Installation

### 1. Install as an Agent Skill

Send this to any Skill-supporting Agent (TRAE, Claude Desktop, Alma, Codex…):

```text
Please install the Skill from: https://github.com/ivercurry99/yy-text2-xhs-img
```

Or, if you have the `skills` CLI:

```bash
npx skills add ivercurry99/yy-text2-xhs-img
```

Or clone it manually into your Skills folder:

```bash
# Example paths — adapt to your host:
#   TRAE:       ~/.trae/skills/   (Windows: %USERPROFILE%\.trae\skills\)
#   Claude:     ~/.claude/skills/
#   Alma:       ~/.config/Alma/skills/
git clone https://github.com/ivercurry99/yy-text2-xhs-img.git <your-skills-dir>/yy-text2-xhs-img
```

### 2. Install optional Python deps (only for --mode api)

```bash
cd yy-text2-xhs-img
pip install -r requirements.txt
```

The only *hard* runtime dependency for the pipeline core is Python 3.10+.
The image-validation part auto-uses Pillow if installed, and falls back to a
pure-Python PNG IHDR parser otherwise (so the dry-run and agent-mode always
work, even in a bare Python stdlib environment).

### 3. Optional API keys

See `references/fallback-strategy.md` — keys are only required if you want
DALL·E 3 / FAL FLUX in `--mode api`.  TRAE native + Seedream plugin (the
first two free tiers of the default fallback chain) need zero setup.

---

## Quick start

### Validate prompts before spending credits

```bash
cd yy-text2-xhs-img
python scripts/generate.py \
  --topic "Summer oily skincare 3-step routine for women 20s" \
  --cards 4 \
  --style ins-aesthetic \
  --ratio 3:4 \
  --dry-run-prompts
```

This prints the fully-composed cover + 3 inner card prompts & negatives,
so you can check the palette lock line and the scene details before any
model runs.  Always do this once for new briefs.

### Agent mode (default) — use your host's built-in image tools

```bash
python scripts/generate.py \
  --topic "七夕限定国潮口红套组推荐" \
  --cards 5 \
  --style neo-chinese \
  --ratio 3:4
```

This will:
1. Create `output/<run-id>/tasks.json` with one task per card (prompt,
   negative, TRAE size preset, ratio, width, height).
2. Print the path.  Your host agent reads each task, calls its
   `GenerateImage` or Seedream plugin, and drops `cover.png`, `card_1.png` …
   into the run dir.
3. Run again with `--resume <run-id>` to validate the PNGs & write
   `manifest.json`.

### API mode — direct DALL·E 3 / FLUX (with keys in env)

```bash
# First export keys once per shell (PowerShell example):
$env:OPENAI_API_KEY = "sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
$env:FAL_KEY          = "xxxxxxxxxxxxxxxx:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# Then generate:
python scripts/generate.py \
  --topic "七夕限定国潮口红套组推荐" \
  --cards 5 \
  --style neo-chinese \
  --ratio 3:4 \
  --mode api \
  --providers fal-flux,dalle3   # pick only paid providers, skip the agent-only ones
```

Failed calls retry 3 times with 2 → 4 → 8 second backoff; if a provider is
fully down the chain jumps to the next one; and every output is PNG-validated
and aspect-ratio checked before being written to the manifest.

### Strict mode (pixel-perfect ratio)

By default ratio tolerance is 1 % (within bucket rounding).  If you *must*
have exact 3:4 frames because your post layout crops hard:

```bash
python scripts/generate.py … --strict
```

A soft warn becomes a hard reject → retried → if 3 retries fail, fall back to
the next provider.

---

## Repo layout

```text
yy-text2-xhs-img/
├── SKILL.md                        # Skill manifest + execution rules for the agent
├── README.md                       # ← you are here
├── LICENSE                         # MIT
├── requirements.txt                # Optional Python deps
│
├── styles/
│   └── presets.json                # 8 presets + negativeBase + sizeMap
│
├── scripts/
│   └── generate.py                 # Main CLI: schema → prompt → providers → validate → manifest
│
├── references/
│   ├── prompt-engineering.md       # How prompts are built & why, plus failure fixes
│   ├── model-matrix.md             # Which model for which scenario (capability table)
│   └── fallback-strategy.md        # Fallback chain behaviour + key config + resume semantics
│
├── tests/
│   └── test_generate.py            # Unit tests (no network) — 6 classes of pure-function logic
│
├── evals/
│   └── evals.json                  # Regression eval cases for prompt-build / size-map / fallback chain
│
└── .github/
    └── workflows/ci.yml            # Ubuntu-22.04 × Py 3.10 / 3.11 / 3.12 — syntax, preset-validate & pytest
```

---

## Running the tests locally

```bash
pip install -r requirements.txt   # at minimum: pytest, Pillow are nice-to-haves
pytest tests/test_generate.py -v --cov=scripts --cov-report=term
```

The test suite covers:

- preset schema integrity (every field present, nothing empty)
- 8 built-in presets × size-map × universal negative
- prompt composition: cover / step-1 / middle / final-shot role lines
- palette lock line presence & 5 hex listed
- negative dedup & layering (base → preset → user exclude)
- exclude & has_text behaviour
- topic-keyword scene visualiser
- PNG magic & size validators (including pure-Python IHDR fallback)
- size-map lookups & aspect-ratio match on a fake 1080×1440 PNG
- provider fallback on a fully keyless env → ends in "all providers failed" (expected, not a bug)
- full CLI dry-run JSON round-trip on a 5-card neo-chinese lipstick brief

---

## Roadmap & Contributing

Planned short-term:
- [ ] Add a second adapter round: for `fal-ai/flux-pro` and `seedream 5` when exposed.
- [ ] Set-level consistency: allow `--same-seed <N>` to re-run against manifest seeds for expansions.
- [ ] Add a 9th preset: `k-beauty-glow` (requested) & a how-to for adding brand-custom presets in a subfile.
- [ ] End-to-end: Github Actions smoke-test for `--dry-run` on every PR.

Contributing:
1. Open an issue first describing the scenario your change fixes (helps
   avoid double work & prompts off-topic PRs).
2. Add the matching test case to `tests/test_generate.py` so your fix stays
   fixed.  If it's a new preset, extend `TestPresetSchema` with an explicit
   assertion block & add an eval case to `evals/evals.json`.
3. Pass the full test suite locally: `pytest tests/ -v` on both a bare Python
   (no Pillow) and a Pillow-installed env so the pure-Python PNG parser path
   still works.
4. Send the PR.  CI will also re-run the matrix.

---

## License

MIT © 2026 YYIver.  See `LICENSE`.