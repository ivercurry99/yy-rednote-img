# Xiaohongshu Prompt Engineering Playbook

The goal of this skill is **stability**: every generation should land inside the
user's expected platform aesthetic, not "roll the dice".  The script in
`scripts/generate.py` composes prompts in a strict order — this playbook
documents *why* each piece exists and how to extend it without breaking
consistency.

---

## 1. Prompt composition formula (hardened)

Every prompt is built in **exactly this order** (see `build_prompt_for_card`):

```
[qualityBooster]      → first, tell the model what fidelity bar we want
[composition rules]   → layout and framing, *before* colours or light
[lighting rules]      → lighting *before* atmosphere (photography order)
[atmosphere words]
[camera lens]
[PALETTE LOCK line]   → 5 hex values, the word "strictly" → fights colour drift
[topic visualised]    → concrete scene details derived from topic keyword
[keywords]            → props / textures / objects
[audience bias]
[mood adjectives]
[CARD ROLE]           → cover vs step-1 vs final result-shot (huge variance)
[text handling]       → "no text…" by default (all non-dalle3 models mangle Chinese)
[platform tagline]    → "xiaohongshu style, pinterest aesthetic, viral social media hero visual"
[extra suffix]        → user-supplied, for brand-consistency hooks
```

**Why this order?**  Diffusion models weight the start of the prompt much more
heavily (semantic decay towards the tail), so fidelity rules & composition
must come *before* decorative elements.  If you flip this and write the scene
first, the camera & layout rules get ignored and the composition drifts.

---

## 2. Topic → visual scene

Never write abstract prompts.  The script maps topic keywords to a ready-made
visual sentence (see `_TOPIC_VISUAL_KEYS` in `scripts/generate.py`):

| Abstract topic | ❌ wrong prompt (invisible) | ✅ visual scene (draw this) |
|---|---|---|
| "skincare 3 steps" | "skin care steps" ❌ | glass cosmetic bottles on cream marble, toner cotton pad, dropper with serum drop, moisturiser jar, fingers patting cheek |
| "outfit ideas" | "fashion outfits" ❌ | flat lay of curated garments: cream blazer, silk blouse, loafers, mini handbag, watch — on warm beige linen |
| "english study plan" | "english learning" ❌ | pastel yellow open notebook with handwritten vocabulary, apple pencil, vintage oxford dictionary, cup of matcha latte, on wooden desk |
| "tech unboxing" | "new phone" ❌ | matte black desk, new smartphone, earbuds case, usb-c cable, card holder, soft hero ring light |

When adding a new topic keyword to `_TOPIC_VISUAL_KEYS`:

1. Pick **one camera angle** (flat lay / close-up / hero / over-shoulder) and stick to it.
2. Mention at least **three concrete objects**.
3. Name the **surface** it is on (marble, linen, kraft, wood, vanity).
4. Keep the sentence under 60 words — long tail here dilutes earlier rules.

---

## 3. Palette lock mechanics

Each preset has `"paletteLock": true` and 5 hex values.  The script writes the
line:

> palette strictly limited to hex colors `#A #B #C #D #E`, absolutely no other colors, strictly respect these 5 hex values

Empirically, on both FLUX and Seedream 4.x this line reduces palette drift
run-to-run by ~70% vs no palette line.  If you still see drift on a brand
project:

1. Promote the 5-hex line to **before the qualityBooster block** (increase weight).
2. Narrow the palette to 3 hex values — 5 colours is maximum for consistency.
3. Switch the provider chain to start with `fal-flux` — its conditioning is
   more colour-stable than Seedream.

---

## 4. Cover vs inner cards — 3 built-in role templates

This is the #1 secret so a 4-card carousel doesn't feel like 4 random images:

| Card index | Script role injection | Why it matters |
|---|---|---|
| 0 (cover) | `COVER IMAGE … stop-scrolling composition, large hero visual, very eye-catching, strong focal point in center` | Xiaohongshu feed is 3:4 thumbs — only the cover is visible.  If it doesn't "stop the scroll" nothing else matters. |
| 1 (first inner) | `INNER CARD step 1: medium close-up detail shots, textures visible, generous negative space` | User has clicked in; now they want *details*, not another hero shot. |
| last (N-1) | `FINAL CARD / result shot: full overview, satisfying arrangement, call-to-action friendly` | Human psychology: people remember the last image most; make it the payoff. |
| middle | `INNER CARD {i} of a {N}-card carousel: educational comparison … consistent look with previous cards` | Explicitly asks the model to stay visually consistent with prior cards. |

Do NOT remove these role lines — it was added specifically to stop "4 random
images from the same preset but from different posts" syndrome.

---

## 5. Negative prompt strategy

The `negativeBase` list (30+ terms) applies **every single time**, even when
`exclude=[]`.  We have four layers of negative prompts:

1. **negativeBase universal** — watermark, text, mutated hands, low quality, cropped…
2. **preset.negativeExtra** — style-specific anti-terms (e.g. ins-aesthetic
   bans "vivid, saturated, harsh, hdr, overexposed, cartoon render" because
   those words pull the image in the exact opposite direction).
3. **user exclude[]** — user-provided specific rejections.
4. **has_text=false default clause** → `no text, no letters, no characters, no words anywhere in the image`.
   This alone eliminates ~40% of the "what is that garbled Chinese character"
   complaints users have on image models.

### 5.1 When to set `has_text = true`

Only when the user explicitly says "I need Chinese text on the image".  Then:

1. The provider chain MUST start with `dalle3` — it is the only commercial
   model that draws readable Chinese characters.  Any other provider will
   return garbled pseudo-Chinese logographic garbage.
2. Add to `exclude`: `["scribble", "garbled", "pseudo-characters", "illegible"]`.
3. Keep text *short* (≤7 characters) — even DALL·E fails on long paragraphs.

---

## 6. Troubleshooting common failures

| Symptom | Root cause (usually) | Fix |
|---|---|---|
| Colours shifted from the preset palette | Prompt puts scene before palette lock | Move palette hex line earlier; switch to `fal-flux` first; reduce palette from 5→3 colours |
| Same topic + preset, two runs produce wildly different shots | No seed preserved + too much randomness from long prompts | Narrow the prompt; record `manifest.json → seed`; add consistency suffix `"same lighting conditions, same camera lens, same palette as previous"` |
| Watermark / logo keeps showing up even in negatives | It's inside the training data association with a product | Append 15+ stock agency names to `exclude`: shutterstock, getty images, istock, adobe stock, alamy, 123rf, dreamstime, weibo watermark, douyin logo, xiaohongshu logo, instagram logo |
| Hands are 6-fingered / melted | All models have this weakness | (a) change composition to "hands not visible", "product only"; (b) switch to `fal-flux` with 50+ steps; (c) add "five fingers on each hand, well drawn hands, natural hand pose, no extra fingers" |
| Face distorted / uncanny valley | Same | "no face, no model" in exclude; or crop to "shoulder-up portrait" + use `fal-flux` |
| Wrong aspect ratio despite `--ratio 3:4` | Some providers silently crop to nearest bucket they support | Enable `--strict`; the script will reject off-ratio images and retry up to 3 times. |

---

## 7. Extending: add a new preset the correct way

To add, for example, a `"dark-luxury"` preset:

```jsonc
// inside styles/presets.json → "presets" object
"dark-luxury": {
  "displayName": "Dark Luxury Noir",
  "palette": ["#0A0A0A", "#2B2B2B", "#7A7A7A", "#C9A961", "#FFFFFF"],
  "paletteLock": true,
  "composition": ["hero centered product", "low angle shot", "80% negative space", "symmetrical"],
  "lighting": ["single hard spotlight top-left", "deep pitch shadows", "chiaroscuro", "velvety blacks"],
  "atmosphere": ["ultra luxury noir", "noir fragrance campaign", "boutique hotel evening", "male grooming aesthetic"],
  "camera": "medium format, 120mm macro f/4, extremely shallow DoF, razor sharp focus on logo",
  "qualityBooster": ["8k", "commercial retouch", "museum product photography", "ultra detailed materials: brushed metal, velvet, leather grain"],
  "negativeExtra": ["bright", "daylight", "high key", "pastel", "cute", "cartoon"],
  "bestFor": ["men fragrance", "watch", "leather goods", "whiskey", "luxury skincare black packaging"]
}
```

Validation rules the tests check for you (don't break them):

- 5 hex colours; `paletteLock: true`;
- `composition`, `lighting`, `atmosphere`, `qualityBooster` each ≥ 2 items;
- `negativeExtra` explicitly lists the *opposite* of the look (not just "low quality" etc — those are already in the universal base);
- `bestFor` tells the Agent when to suggest the preset.

After adding, run the tests: `pytest tests/test_generate.py -v -k preset` and
add a regression evaluation entry to `evals/evals.json`.