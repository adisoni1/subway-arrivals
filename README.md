# NYC Subway & Bus Arrivals Sign

A live NYC transit arrivals sign for a **128×32 RGB LED matrix**. It **cycles
through several stations** (subway + bus), showing each one's next arrivals. It
runs on a laptop using
[`RGBMatrixEmulator`](https://github.com/ty-porter/RGBMatrixEmulator) (renders in
a browser tab) and on a **Raspberry Pi** with the real
[`rpi-rgb-led-matrix`](https://github.com/hzeller/rpi-rgb-led-matrix) library —
**with zero code changes**. The display layer tries to import the real hardware
bindings and falls back to the emulator, so the only difference between laptop
and Pi is which library is installed.

- **Subway** data comes from the MTA GTFS-Realtime feeds via
  [`nyct-gtfs`](https://github.com/Andrew-Dickinson/nyct-gtfs) — **no API key**.
- **Bus** data (M15 etc.) comes from the MTA Bus Time SIRI API, which **does
  require a free API key** (see [Bus setup](#bus-setup-m15)).

```
┌──────────────────────────────────────────────────┐
│ 53 ST  E F                                        │  amber header
│ (F)  Jamaica-179 St                          1m   │
│ (E)  World Trade Center                       4m   │   128 × 32
│ (E)  Jamaica Center                           7m   │
└──────────────────────────────────────────────────┘
```

The sign advances to the next screen every `cycle_seconds`. Both directions are
shown per station — the destination tells you which way each train is headed.

## Project layout

| File                  | Purpose                                                        |
| --------------------- | ------------------------------------------------------------- |
| `config.json`         | The list of `screens` to cycle + timing                       |
| `emulator_config.json`| Emulator render style (pixel size/style, browser port)        |
| `display.py`          | Matrix init (hardware/emulator swap) + draw helpers           |
| `mta.py`              | Subway: fetch + parse live arrivals → `Arrival` objects       |
| `bus.py`              | Bus: MTA Bus Time SIRI arrivals (needs API key)               |
| `main.py`             | Main loop: cycle screens, refresh ~30s, redraw every 1s       |
| `find_stop.py`        | Look up a subway station's GTFS stop id                       |
| `test_static.py`      | Render a hardcoded screen (no network) to check layout        |
| `fonts/`              | Bundled BDF fonts (used on both laptop and Pi)                |

## Setup (laptop)

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

## Configure the screens

`config.json` holds a list of `screens` the sign cycles through, plus timing:

```json
{
  "cycle_seconds": 8,
  "refresh_seconds": 30,
  "max_arrivals": 3,
  "screens": [
    { "type": "subway", "name": "53 ST  E F", "station_stop_id": "F11",
      "direction": "both", "routes": ["E", "F"] },
    { "type": "bus", "name": "M15  1/2 AV  57/56 ST",
      "stop_codes": ["401704", "405387", "401765"], "routes": null }
  ]
}
```

- `layout` — text size preset (see [Layout](#layout) below).
- `labels` — row text: `destination` (headsign, default) or `direction`
  (Uptown/Downtown). See [Row labels](#row-labels) below.
- `cycle_seconds` — how long each screen shows before advancing.
- **Subway screen**: `station_stop_id` (parent id, no `N`/`S` suffix — find it
  with `find_stop.py`), `direction` (`N`, `S`, or `both`), and `routes`.

  ```bash
  ./venv/bin/python find_stop.py "lexington av/53"
  #   stop_id   station_name
  #   F11       Lexington Av/53 St
  ```

- **Bus screen**: `stop_codes` is a list of MTA Bus Time stop codes (the 6-digit
  number on the bus-stop sign / at bustime.mta.info). `routes` filters by route
  name, or `null` to show every bus at those stops.

The shipped config cycles five screens: 59 St 4/5/6, 59 St N/R/W, 53 St E/F,
63 St M/Q, and the M15 bus.

## Layout

Two text-size presets, since legibility on a 128×32 panel is a trade-off
between text size and how much fits:

| Layout    | Font  | Rows | Notes                                            |
| --------- | ----- | ---- | ------------------------------------------------ |
| `compact` | 5×7   | 3    | Default. Crisp, shows 3 arrivals, full names fit |
| `large`   | 6×10  | 2    | Biggest text, 2 arrivals, long names truncate    |

Set it in `config.json` (`"layout": "compact"`), or override per-run without
editing anything:

```bash
./venv/bin/python main.py --layout large
./venv/bin/python main.py --layout compact
```

Handy for comparing the two on the real panel before committing to one.

## Row labels

Each row's middle text can be either the **destination headsign** or a simple
**Uptown / Downtown** label derived from the train's direction:

| `labels`      | Row shows                                  |
| ------------- | ------------------------------------------ |
| `destination` | `World Trade Center`, `Jamaica-179 St`, …  |
| `direction`   | `Uptown` / `Downtown`                      |

Set it in `config.json` (`"labels": "direction"`) or per-run:

```bash
./venv/bin/python main.py --labels direction
```

Mapping: subway `N` → Uptown, `S` → Downtown; bus northbound → Uptown,
southbound → Downtown. This fits Manhattan stations (it's how the MTA labels
those platforms). For crosstown/outer-borough lines, "Uptown/Downtown" is less
meaningful — stick with `destination` there.

## Bus setup (M15)

Unlike the subway, MTA Bus Time needs a **free API key**:

1. Register at <https://register.developer.obanyc.com/> (instant).
2. Export the key before running (no secret goes in the repo):

   ```bash
   export MTA_BUS_API_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   ```

Without the key, the bus screen simply shows no arrivals; the subway screens
work regardless.

## Run

```bash
# Optional: check the layout with dummy data first (Milestone A)
./venv/bin/python test_static.py

# Live sign
./venv/bin/python main.py
```

Then open **http://localhost:8888** in a browser. The minutes count down every
second; the underlying data refreshes every `refresh_seconds`. A failed refresh
keeps showing the last good arrivals instead of crashing or blanking.

## Moving to the Raspberry Pi

**No code changes** — the import fallback in `display.py` switches to real
hardware as soon as the matrix library is present. But you do need to set up the
Pi (do this once):

1. **Build hzeller's matrix bindings** (this is what triggers the hardware path):

   ```bash
   git clone https://github.com/hzeller/rpi-rgb-led-matrix
   cd rpi-rgb-led-matrix && make build-python PYTHON=$(command -v python3)
   sudo make install-python PYTHON=$(command -v python3)
   ```

2. **Install the Python data deps** into the *same* interpreter you'll run as
   root (the matrix needs root for GPIO, so everything must be importable by
   root's `python3`):

   ```bash
   sudo pip3 install nyct-gtfs requests    # RGBMatrixEmulator not needed on the Pi
   ```

   (If you prefer a venv, create it with `--system-site-packages` so the
   system-installed `rgbmatrix` module is visible, and run the venv's python
   with sudo.)

3. **Copy this project to the Pi and run it** (root for GPIO):

   ```bash
   sudo python3 main.py
   ```

   For the M15 bus screen, pass the key through `sudo` (env is stripped
   otherwise):

   ```bash
   sudo MTA_BUS_API_KEY=your-key python3 main.py
   ```

   Subway-only? You can drop the bus screen from `config.json` and skip the key.

### Auto-start on boot (systemd)

To have the sign start on boot and restart if it crashes, use the unit in
[`deploy/subway-sign.service`](deploy/subway-sign.service):

```bash
# Put your bus key where the service can read it (not in the repo):
echo 'MTA_BUS_API_KEY=your-key' | sudo tee /etc/subway-sign.env

# Edit WorkingDirectory in the unit if your project isn't at /home/pi/subway-arrivals
sudo cp deploy/subway-sign.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now subway-sign

sudo systemctl status subway-sign      # check it's running
journalctl -u subway-sign -f           # follow logs
```

### This build's hardware

`init_matrix()` in `display.py` is already configured for this setup:

- **Two 64×32, P4 (4mm) panels chained side by side** → 128×32
  (`rows=32, cols=64, chain_length=2`). Finished size ≈ 512 × 128 mm (~20 × 5").
- **Adafruit RGB Matrix Bonnet/HAT** → `hardware_mapping="adafruit-hat"`.
- Plug the two panels in series: Pi/Bonnet → panel 1 `IN` → panel 1 `OUT` →
  panel 2 `IN`. Power both panels from a **5V supply** (a 128×32 P4 pair can pull
  ~4A at full white; a 5V/4A+ supply is sensible). Don't power the panels from
  the Pi.

### Pi tuning (in `display.py` → `init_matrix`)

If something looks off on the panels:

- **Flicker** → raise `options.gpio_slowdown` (Pi 3: `1`–`2`, Pi 4: `3`–`4`).
- **Worse flicker / ghosting** → if you soldered the bonnet's optional jumper
  ("E" / quality mod), set `hardware_mapping="adafruit-hat-pwm"`.
- **Reds showing as blue / wrong colors** → set a panel color order, e.g.
  `options.led_rgb_sequence = "RBG"` (try permutations until red is red).
- **Only one panel lights / the two halves are swapped or mirrored** → check the
  `IN`/`OUT` chaining order above; `chain_length` must be `2`.

## Display geometry

The sign is two 64×32 panels chained horizontally → a 128×32 canvas
(`rows=32, cols=64, chain_length=2`). This is set in code (`display.py`) so it
matches the real Pi wiring; the emulator derives the same 128×32 canvas from
those numbers. `emulator_config.json` only controls render *style* (pixel size,
shape, browser port).
