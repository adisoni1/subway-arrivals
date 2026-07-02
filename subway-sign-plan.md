# NYC Subway Arrivals Sign — Laptop Emulator Build Plan

## Goal
Build a Python app that pulls **live MTA subway arrivals** for one station + direction and
renders them on a **simulated 128×32 RGB LED matrix** on my laptop using `RGBMatrixEmulator`.
Structure the code so the **same program runs unchanged on a Raspberry Pi** with the real
`rpi-rgb-led-matrix` library later — the only difference should be which library is installed.

## Key facts / constraints
- Target display: **128×32**, i.e. two 64×32 panels chained horizontally (`rows=32, cols=64, chain_length=2`).
- MTA subway GTFS-Realtime feeds require **no API key**.
- Use the **`nyct-gtfs`** Python library for fetching + parsing the feed (it handles the feed
  URLs and works without a key). Do not hardcode feed URLs if the library can resolve them.
- The display layer must **auto-select real hardware vs. emulator** so no code changes are
  needed when moving to the Pi.
- No secrets in the repo.

## Tech stack
- Python 3.10+
- `RGBMatrixEmulator` — renders the matrix in a browser tab / window on the laptop
- `nyct-gtfs` — live MTA subway data
- (later, on the Pi only) `rpi-rgb-led-matrix` Python bindings — same API as the emulator

## Project structure
```
subway-sign/
  config.json           # station, direction, routes, refresh interval
  emulator_config.json  # emulator display geometry (128x32) + adapter
  display.py            # matrix init (hardware/emulator swap) + draw helpers
  mta.py                # fetch + parse arrivals -> [(route, destination, minutes)]
  main.py               # loop: refresh data periodically, redraw every second
  requirements.txt
  README.md
```

## The hardware/emulator swap (do this first, it shapes everything)
In `display.py`, select the backend by trying the real library and falling back to the emulator:
```python
try:
    from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics  # real Pi hardware
except ImportError:
    from RGBMatrixEmulator import RGBMatrix, RGBMatrixOptions, graphics  # laptop
```
On the laptop `rgbmatrix` isn't installed, so it uses the emulator. On the Pi it'll use real
hardware. Class names and methods are identical, so nothing downstream changes.

## emulator_config.json
Configure the emulator for a 128×32 chain:
- `pixel_style`: square or round (round looks more LED-like)
- display size = 64 cols × 32 rows × chain 2 → 128×32
- adapter: `browser` (opens in a tab) or `pygame` (native window) — pick `browser` for simplicity.

## Tasks (in order)
1. **Scaffold**: create the project, a virtualenv, and `requirements.txt`
   (`RGBMatrixEmulator`, `nyct-gtfs`). Install them.
2. **Display backend** (`display.py`): implement the import-fallback above. Initialize
   `RGBMatrix` with `RGBMatrixOptions(rows=32, cols=64, chain_length=1, ...)` — note the
   emulator treats the whole 128×32 as one canvas; match its config to the real wiring.
   Expose a `draw_arrivals(canvas, arrivals)` helper.
3. **Milestone A — static render first**: before touching live data, render **3 hardcoded
   dummy rows** (e.g. `A Far Rockaway 3 min`) to confirm the emulator, layout, fonts, and
   colors look right. Each row = colored route bullet (filled circle + route letter) +
   destination text + right-aligned minutes. Use a BDF font bundled with the library
   (e.g. a ~7px font) so 3 rows fit in 32px. Get this looking good, then move on.
4. **MTA data** (`mta.py`): using `nyct-gtfs`, fetch the feed for the relevant line, find
   trains whose `stop_time_updates` include my station's stop id for my direction, compute
   **minutes-from-now** for each, sort ascending, and return the soonest few as
   `[(route, destination, minutes), ...]`. Handle network/parse errors gracefully and keep
   serving the **last good result** if a refresh fails.
5. **Milestone B — go live** (`main.py`): load `config.json`; fetch arrivals every
   `REFRESH_SECONDS` (default 30); **recompute minutes and redraw every 1 second** from the
   cached data so the countdown is smooth without hammering the feed. Show the top 3.
6. **Route bullet colors**: map routes to official MTA colors (below). Yellow-line bullets
   (N/Q/R/W) use **black** text; all others use white.
7. **README**: how to run on the laptop, and the single step to move to the Pi
   (install `rpi-rgb-led-matrix`; the import fallback does the rest).

## Config I will fill in
- `station_stop_id` — my station's GTFS stop id (has a direction suffix, e.g. `A41` + `N`/`S`).
  Help me find it: fetch the MTA static GTFS `stops.txt` (or use a stop-id lookup) and print
  matches for a station name I give you.
- `direction` — `N` or `S`
- `routes` — which lines to display (e.g. `["A","C","L"]`)
- `refresh_seconds` — default 30

## MTA route → bullet color reference
- 1/2/3 → red `#EE352E`
- 4/5/6 → green `#00933C`
- 7 → purple `#B933AD`
- A/C/E → blue `#0039A6`
- B/D/F/M → orange `#FF6319`
- G → light green `#6CBE45`
- J/Z → brown `#996633`
- L → gray `#A7A9AC`
- N/Q/R/W → yellow `#FCCC0A` (black text)
- S (shuttle) → dark gray `#808183`

## Definition of done
- `python main.py` on the laptop opens a **128×32 emulated matrix** showing my station's next
  **3 real arrivals**: colored route bullet, destination, and a live-counting minutes value.
- Minutes tick down every second; underlying data refreshes ~every 30s; a failed refresh
  doesn't crash or blank the screen.
- **Zero code changes** are needed to run it on the Pi — only installing the real library.

## Notes for the Pi (later, don't do now)
- Install hzeller's `rpi-rgb-led-matrix` Python bindings; the import fallback auto-switches.
- Expose `led-slowdown-gpio` and panel **color order** as options — generic panels sometimes
  need a color-order tweak (reds showing as blue) and a higher slowdown value to avoid flicker.
- Hardware mapping for the Adafruit bonnet is the `adafruit-hat` option.
```
```
