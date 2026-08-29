# Fallback Chain Design & API Key Management

The pipeline never fails hard because of a single provider outage.  The loop
in `run_provider_chain()` (inside `scripts/generate.py`) is the only place
where provider decisions are made — this page explains exactly how it works
and how to configure secrets safely.

---

## 1. Default fallback order

```
1. trae-native       (host agent has GenerateImage tool → use it, 0 config)
      ↓
2. seedream-plugin   (TRAE Seedream plugin authorized → use it)
      ↓
3. dalle3            (if OPENAI_API_KEY env var is set)
      ↓
4. fal-flux          (if FAL_KEY env var is set)
      ↓
Fatal: ALL providers failed — print a structured failure log + exit code 1.
```

You can override it via `--providers a,b,c`:

```bash
# Budget mode: only free providers
python scripts/generate.py --providers trae-native,seedream-plugin …

# Production brand post mode: only the two paid providers
python scripts/generate.py --providers fal-flux,dalle3 …
```

---

## 2. When does the loop move to the next provider?

There are **two severities of failure** inside each provider's attempt loop:

| Severity | Triggers | Behavior |
|---|---|---|
| **Skip immediately** (no retries) | Missing tool / missing key / `401` auth / `403` permission / `429` rate-limit with no reset-time header. | Record the skip reason in `manifest.failures`, go to next provider. |
| **Retryable** (up to 3 per provider) | `5xx` / network timeout / 200 OK but PNG header corrupt / `< 50 KB` / wrong aspect ratio (strict mode). | Exponential backoff: 2 s, 4 s, 8 s sleep between retries.  After 3 fails, move to the next provider. |

### Why not just retry forever?

Because every real-world provider outage has lasted *hours*.  If a user is
waiting 10+ seconds per image × 3 retries × 4 providers, that's already a
couple of minutes before they get a clear message like

> "seedream-plugin returned 429 (quota exhausted), skipped after attempt 1;
> dalle3 503 for 3 attempts; fal-flux succeeded on attempt 1 in 2300 ms".

That message (in `manifest.json → cards[i].result_reason`) lets the user know
exactly where the pipeline was slow and what to fix — e.g. refill seedream
quota or raise FAL rate limits.

---

## 3. Secrets configuration

### 3.1 Never commit keys.  Never.

`.gitignore` already contains:

```
.env
.env.*
secrets.json
*.pem
*.key
```

If you ever add a `*.env.example` or similar, **use placeholders only**.

### 3.2 Set up keys (per shell)

#### PowerShell (Windows)

```powershell
# DALL·E 3 (OpenAI)
$env:OPENAI_API_KEY = "sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# FLUX (FAL)
$env:FAL_KEY          = "xxxxxxxxxxxxxxxx:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

#### macOS / Linux (zsh / bash)

```bash
export OPENAI_API_KEY="sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export FAL_KEY="xxxxxxxxxxxxxxxx:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

Verify:

```bash
python scripts/generate.py --topic "test" --cards 1 --style clean-minimal --ratio 1:1 \
  --dry-run-prompts --mode api --providers dalle3,fal-flux
# → should NOT print "OPENAI_API_KEY missing" in its error log on a real run
```

### 3.3 (Optional) `.env` file

Install `python-dotenv` and load `.env` yourself before the script — the
script intentionally does **not** auto-load `.env` so CI and unit tests don't
need a filesystem.  If you really want it, run:

```bash
pip install python-dotenv
# then before generate.py:
python -c "from dotenv import load_dotenv; load_dotenv()" && python scripts/generate.py …
```

Or source `.env` into the shell manually.  Just don't commit `.env`.

---

## 4. Resuming a run that Ctrl+C'd mid-flight

Every run writes a `manifest.json` *during* generation (one `cards` append
per image).  If you interrupt the process you can restart from the last
successfully written card:

```bash
python scripts/generate.py --topic "…" --cards N …  --resume 20260829-201140-844b0b
```

Behavior with `--resume`:
- Any image file already present in the run dir that passes the PNG + ratio
  check is skipped.  This means you can manually replace a bad output and the
  resume step will happily accept yours.
- Missing cards will be regenerated.
- The existing `manifest.json` is preserved for succeeded cards; new entries
  are appended in-place.

This is also how agent-mode works: first run writes a `tasks.json` describing
every card to produce (with exact prompt, trae_size, ratio); the host agent
calls `GenerateImage` (or Seedream / etc.) for each, drops the PNG into the
run directory, then a second `--resume` pass validates & finalises the
manifest.

---

## 5. Failure modes summary (for debugging)

| What you see in `result_reason` | Root cause / action |
|---|---|
| `"requires agent tool surface, skipped in script API-mode"` | Normal for `trae-native` / `seedream-plugin` in `--mode api`.  They require the host agent surface.  Use `--mode agent` + `tasks.json` handoff. |
| `"OPENAI_API_KEY missing"` | Export it, or drop that provider from the chain. |
| `"FAL_KEY missing"` | Same — either add the key, or remove `fal-flux` from providers. |
| `"image validation failed: too small"` | Provider returned a cached placeholder or 500-error HTML page disguised as PNG.  Retry 3x, then switch to next provider. |
| `"image validation failed: bad PNG header …"` | Download was truncated.  Check disk space / network proxy.  Retryable. |
| `"ratio warning: 12.34% off …"` (non-strict) | Soft warning, not a failure by default.  If you want pixel-perfect ratio, add `--strict`. |
| `"all providers failed. log: …"` | Every provider was skipped or errored 3 times.  Read the embedded JSON log to see exactly which provider failed at which step with what reason — usually a missing API key or network. |