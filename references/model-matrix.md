# Model Capability Matrix & Selection Guide

This skill ships a 4-provider adapter.  These are not "all equivalent with
different logos".  Each model has strengths and weaknesses that are visible
*even with exactly the same prompt*.  Use the right tool for the job.

> Scores are relative, 1–5, based on side-by-side subjective tests on
> Xiaohongshu-style workloads (skincare products, fashion flat lays,
> editorials, food, illustrations).  Your mileage on other domains may vary.

---

## 1. Capability table

| Capability | TRAE native `GenerateImage` | Seedream 4.x plugin | DALL·E 3 | FLUX Dev (FAL) |
|---|---|---|---|---|
| **Provider id** | `trae-native` | `seedream-plugin` | `dalle3` | `fal-flux` |
| Cost | FREE | FREE with TRAE | paid (~$0.04 / HD image) | paid (~$0.03 / image) |
| Requires key | no | plugin auth | `OPENAI_API_KEY` | `FAL_KEY` |
| Speed (first byte) | very fast (s) | fast (<15s) | medium (15–30s) | medium (15–40s) |
| Chinese **semantic** understanding | 4 | **5** | 2 | 3 |
| **Chinese characters drawn in image** | 1 | 1 | **4** | 2 |
| English typography | 2 | 2 | **5** | **4** |
| Human anatomy realism | 3 | 4 | 4 | **5** |
| Hand / finger correctness | 3 | 3 | 4 | **5** |
| Palette lock stability | 3 | 4 | 3 | **5** |
| Consistency across a 4-card set | 3 | 3 | 4 | **4** |
| Product / e-commerce realism | 3 | 4 | 4 | **5** |
| Guochao / Chinese motifs | 3 | **5** | 2 | 3 |
| Cinematic / film grain | 3 | **5** | 3 | **5** |
| Flat illustration / sticker style | 4 | 4 | 4 | 3 |
| Y2K / cyber chrome | 3 | 4 | 3 | **5** |
| Minimal pure-white product | 3 | 4 | **5** | 4 |
| Cute macaron illustration | **4** | 3 | 4 | 2 |

### Quick decision flow (most common cases)

```
Need Chinese text in the image? ──yes──> start with dalle3
   │
   └───no, Guochao / festival / Chinese motifs? ──yes──> start with seedream-plugin
            │
            └───no, People / faces / hands heavily featured? ──yes──> start with fal-flux
                     │
                     └───no, Illustration / kids / pastel / low budget? ──yes──> start with trae-native
                              │
                              └───no, Product / white background / e-commerce? ──yes──> dalle3 or fal-flux
                                       │
                                       └───default: trae-native → seedream → fal-flux fallback chain
```

---

## 2. Aspect ratio native buckets

Models only generate a small set of native sizes.  If you ask for a
non-native size you usually get a silent crop that ruins composition.
`styles/presets.json → sizeMap` already locks the 4 Xiaohongshu standard
ratios to the closest native bucket on each model, and the
`validate_ratio()` check catches any residual drift.

| Ratio | Nominal W×H | TRAE size | Seedream aspect | DALL·E 3 size | FLUX FAL image_size |
|---|---|---|---|---|---|
| **3:4** ⭐ feed default | 1080×1440 | `portrait_4_3` | `3:4` ✅ | `1024×1792` ★ closest | `768×1024` → you upscale |
| **1:1** square | 1024×1024 | `square_hd` | `1:1` ✅ | `1024×1024` ✅ | `1024×1024` ✅ |
| **4:3** horizontal | 1440×1080 | `landscape_4_3` | `4:3` ✅ | `1792×1024` ★ closest | `1024×768` → upscale |
| **9:16** story/short | 1080×1920 | `portrait_16_9` | `9:16` ✅ | `1024×1792` (nearest) | `720×1280` → upscale |

★ = DALL·E 3 does not have a perfect 3:4 or 4:3 bucket, so you get a 1792-pixel
long edge image that you then crop to 3:4.  This is still usually preferable to
the other providers' off-composition crops, but enable `--strict` if
pixel-perfect framing matters.

---

## 3. Consistency across a multi-card set

This is the #1 complaint we hear.  Achieving "looks like it came from one
shoot" requires **all** of these:

1. ✅ Fixed preset (same 5 hexes, same composition, same lighting, same camera
   line) → done by `styles/presets.json`.
2. ✅ One provider for the whole set (never let 2 cards run on seedream and 2 on
   FLUX — colour science is different, they can't match).  To enforce, run
   with `--providers fal-flux` (or your single choice) so fallback won't hop.
3. ✅ Consistency suffix appended to every card's prompt:
   ```
   --extra-prompt-suffix "same 5-hex palette, same lighting setup, same camera lens, same shooting angle as the other cards in this post"
   ```
4. ✅ Same seed where supported (FLUX returns a seed; DALL·E 3 doesn't).  Store
   it via `manifest.json` and reuse it on subsequent expansions.

Even with all four you'll occasionally get visible drift — the simplest
mitigation is to enable `--strict` and regenerate only the drifted card
against the successful chain + seed.

---

## 4. Provider limitations & quirks

### `trae-native`
- Free & instant, quality varies by hosting environment.
- **Palette drift** is the main downside.  Use it for drafts / illustation
  styles, not for brand-locked production posts.

### `seedream-plugin`
- Cinematic colour grading and Chinese semantic knowledge are class-leading.
- Draws from Bytedance's Chinese-first training corpus so it absolutely nails
  guochao festival, cha kan (茶歇) food shots, Chinese interior / domestic
  lifestyle scenes.
- **Weakness**: typography and complex English scene text comes out garbled.
  Don't use when `has_text=true`.

### `dalle3`
- The gold standard for typography (Chinese *and* English).
- Composition is very "clean / catalog" oriented — white minimal products
  look amazing; moody editorials can feel a bit flat / well-lit.
- No seed exposed, so cross-run consistency is the worst of the 4 providers.

### `fal-flux` (FLUX Dev via FAL)
- Best anatomy, best palette lock, best style control for fashion & editorial.
- With 32 steps it's the slowest provider here, and costs 1-2c per image on
  average.
- **Weakness**: Chinese-culture specific motifs (Mid-Autumn mooncakes,
  Spring Festival couplets, etc.) sometimes come out Japanese/Korean-looking.
  Pair with seedream-plugin first, or use a very explicit scene prompt with
  keywords like `dunhuang mural palette`, `Chinese red cinnabar lacquer box`,
  `dougong bracket architecture`.