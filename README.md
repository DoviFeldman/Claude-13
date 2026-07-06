# Offshore Lightning Storm Detector ⚡

Detects lightning storms offshore, classifies them by distance band, alerts
via **Telegram**, and publishes a mobile-first **PWA storm map** on GitHub
Pages so you can pick a beach and drive to it.

## How it works

```
GitHub Actions cron (every 5 min, 7 PM–midnight ET, not Friday)
        │
        ▼
detector/main.py
  ├── providers/xweather.py      ← primary (paid API, free tier, great offshore)
  ├── providers/goes_glm.py      ← comparison (NOAA satellite, free, AWS S3)
  ├── providers/blitzortung.py   ← comparison (crowd-sourced, free, experimental)
  │
  ├── classify strikes into distance bands (haversine from secret target coord)
  ├── Telegram alert  ── sweet spot (30–60 km) or approach warning (60–250 km)
  └── commit docs/data/strikes.json ──► GitHub Pages PWA map
```

### Distance bands

| Band | Range | Meaning |
|---|---|---|
| IN IT | 0–5 km | Rain, wind, danger |
| TOO CLOSE | 5–15 km | Loud thunder, real strike risk |
| CAUTION | 15–30 km | Usually dry, but "bolts from the blue" reach ~25 km |
| **SWEET SPOT** | **30–60 km** | **Full silent bolts cloud-to-sea, stars overhead — the trigger** |
| VISIBLE BOLTS | 60–150 km | Bolt channels still visible, pure silent light show |
| CLOUD FLASHES | 150–250 km | "Heat lightning" look, flashes on cloud tops |
| — | 250+ km | Ignored |

The **sweet-spot alert** (30–60 km) is the primary trigger, with a 30-minute
cooldown. A lower-frequency **approach warning** fires when ≥5 strikes sit in
the 60–250 km wide zone (60-minute cooldown). If any strikes are inside
30 km, the alert says so — that's not beach weather.

## Data sources (side-by-side comparison)

All enabled sources run every cycle and their counts appear in each Telegram
alert and on the map, so you can see how each network reports the same storm.
Toggle any of them with repository **Variables** (`ENABLE_XWEATHER`,
`ENABLE_GLM`, `ENABLE_BLITZORTUNG` — set to `false` to disable).

| Source | Cost | Offshore coverage | Notes |
|---|---|---|---|
| [Xweather lightning API](https://www.xweather.com/pricing/weather-api-pay-as-you-go) | first 15,000 accesses/mo free | proven | **Primary.** 1 access/run ≈ 1,600/mo — comfortably free |
| NOAA GOES-East GLM | free (open S3 bucket, no key) | excellent (it's a satellite) | Optical flash detections, ~few km accuracy |
| Blitzortung.org | free | weaker far offshore | **Experimental** unofficial WebSocket; 25 s live sample per run, so counts aren't 1:1 comparable |

Alert *decisions* come from Xweather; if it's down, the detector falls back
to GLM, then Blitzortung.

## Setup

### 1. Secrets (Settings → Secrets and variables → Actions → Secrets)

| Secret | Required? | Value |
|---|---|---|
| `TARGET_LAT` / `TARGET_LON` | **yes** | Your target coordinate (decimal degrees). Never appears in the repo. |
| `XWEATHER_CLIENT_ID` / `XWEATHER_CLIENT_SECRET` | no | From your Xweather account. Missing → source auto-disabled, GLM drives alerts. |
| `TELEGRAM_BOT_TOKEN` | no | From [@BotFather](https://t.me/BotFather) (`/newbot`). Missing → no alerts, map still updates. |
| `TELEGRAM_CHAT_ID` | no | Message your bot once, then visit `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `message.chat.id` |

**Minimal free start:** set only `TARGET_LAT`/`TARGET_LON` and enable Pages —
the NOAA GLM satellite source needs no account or key, so the map gets live
strike data immediately. Add Xweather and Telegram whenever you're ready.

### 2. Variables (same page → Variables tab, all optional)

| Variable | Purpose |
|---|---|
| `MAP_URL` | Public URL of the map (e.g. `https://<user>.github.io/<repo>/`) — linked in every alert |
| `ENABLE_XWEATHER` / `ENABLE_GLM` / `ENABLE_BLITZORTUNG` | `false` to toggle a source off |

### 3. GitHub Pages

Settings → Pages → Source: **Deploy from a branch** → Branch: `main`,
folder **`/docs`**. The map will be at `https://<user>.github.io/<repo>/`.

### 4. Test it

Actions → **Lightning detector** → *Run workflow*. `skip_time_gate` defaults
to on (runs outside the evening window); tick `dry_run` to log the alert
instead of sending it. Add the map to your phone: open the Pages URL →
share → **Add to Home Screen** (it's an installable PWA).

On first open, tap **📍 Home** to set your location (geolocation, or tap the
map). It's stored only in your browser — never uploaded. **📏 Measure** taps
two points and shows km/mi + bearing, and the base map is OpenStreetMap, so
street and beach names match what you'll search in Google Maps.

## Hosting choice: GitHub Pages (not Vercel)

GitHub Pages works here **because no API key ever reaches the client**. The
detector runs inside GitHub Actions (keys stay in Secrets), and the map only
reads a static `strikes.json` the workflow commits. The map itself uses free
OpenStreetMap tiles — no map API key at all. Vercel would only be needed if
the browser had to query a keyed API directly (requiring a serverless proxy);
it doesn't, so Pages wins on simplicity.

## Scheduling

Cron runs every 5 minutes during `23:00–04:59 UTC` — the union of the
7 PM–midnight window in EDT and EST. The script then checks real
`America/New_York` time and exits unless it's 7 PM–midnight on a
non-Friday, so DST and the "evening spans two UTC days" problem are
handled exactly, at the cost of a few seconds of free runner time on the
shoulder runs. (Running 24/7 instead would be simpler to read but ~4× the
Xweather accesses and runner minutes — still free, but the window costs
nothing once written, so it stays.) The wide 250 km approach check
piggybacks on the same single API call — filtering is local, so a separate
wider workflow would add cost for nothing. GitHub may delay scheduled runs
5–15 min under load; fine for this use case.

## Privacy notes

- The exact target coordinate lives only in Actions Secrets.
- `docs/data/strikes.json` contains strike positions (public weather data)
  within 250 km of the target — so the repo does imply the *general region*
  you're in, but never the coordinate itself.
- Your phone's "home" pin is localStorage-only.

## Repo layout

```
detector/               Python package (run: python -m detector.main)
  main.py               orchestration: gate → fetch → classify → alert → publish
  geo.py                haversine, bearings, distance bands
  config.py             all env/secret handling
  alerting.py           Telegram formatting + send
  state.py              alert cooldowns (committed to data/state.json)
  providers/            one module per source, common Strike model
.github/workflows/lightning.yml
docs/                   the PWA (GitHub Pages serves this folder)
scripts/make_icons.py   regenerates the PWA icons
```

## Local run

```bash
pip install -r requirements.txt
# minimal (GLM-only, no alerts):
TARGET_LAT=.. TARGET_LON=.. SKIP_TIME_GATE=true python -m detector.main
# full:
TARGET_LAT=.. TARGET_LON=.. XWEATHER_CLIENT_ID=.. XWEATHER_CLIENT_SECRET=.. \
TELEGRAM_BOT_TOKEN=.. TELEGRAM_CHAT_ID=.. SKIP_TIME_GATE=true DRY_RUN=true \
python -m detector.main
```
