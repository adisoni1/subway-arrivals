"""
NYC Subway/Bus Arrivals sign — main loop.

Loads config.json and cycles through the configured `screens` (stations) on a
128x32 matrix. Each screen's live data refreshes every refresh_seconds; the
display redraws every second so the minutes countdown ticks down smoothly, and
advances to the next screen every cycle_seconds.

Laptop:  ./venv/bin/python main.py   (then open http://localhost:8888)
Pi:      python main.py              (after installing rpi-rgb-led-matrix)

Layout:  --layout large   (bigger 6x10 text, 2 rows) overrides config.json.
"""

import argparse
import json
import os
import time

import display
from mta import MTAArrivals

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# Map a train/bus direction to an "Uptown"/"Downtown" label. Subway stop ids
# carry an N/S suffix; MTA Bus Time gives a DirectionRef of 0/1 (for the M15,
# 0 = northbound/uptown, 1 = southbound/downtown).
DIRECTION_LABELS = {"N": "Uptown", "S": "Downtown", "0": "Uptown", "1": "Downtown"}


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def row_text(arrival, labels):
    """Middle-of-row text: the destination headsign, or Uptown/Downtown."""
    if labels == "direction":
        return DIRECTION_LABELS.get(str(arrival.direction), arrival.destination)
    return arrival.destination


def build_source(screen):
    """Create a data source for one screen based on its `type`."""
    kind = screen.get("type", "subway")
    if kind == "subway":
        return MTAArrivals(
            screen["station_stop_id"], screen.get("direction", "both"), screen["routes"]
        )
    if kind == "bus":
        from bus import MTABusArrivals

        return MTABusArrivals(screen["stop_codes"], screen.get("routes"))
    raise ValueError(f"Unknown screen type: {kind!r}")


def parse_args():
    p = argparse.ArgumentParser(description="NYC subway/bus arrivals sign.")
    p.add_argument(
        "--layout",
        choices=sorted(display.LAYOUTS),
        help="Override the config.json layout (compact=5x7/3 rows, large=6x10/2 rows).",
    )
    p.add_argument(
        "--labels",
        choices=["destination", "direction"],
        help="Row text: 'destination' headsign (default) or 'direction' (Uptown/Downtown).",
    )
    return p.parse_args()


def main():
    args = parse_args()
    cfg = load_config()
    refresh_seconds = cfg.get("refresh_seconds", 30)
    cycle_seconds = cfg.get("cycle_seconds", 8)
    layout_name = args.layout or cfg.get("layout", display.DEFAULT_LAYOUT)
    layout = display.Layout(layout_name)
    labels = args.labels or cfg.get("labels", "destination")
    # Fetch at least enough trains to fill the chosen layout's rows.
    max_arrivals = max(cfg.get("max_arrivals", 3), layout.max_rows)
    screens = cfg["screens"]
    if not screens:
        raise SystemExit("config.json has no screens to display.")

    sources = [build_source(s) for s in screens]
    caches = [[] for _ in screens]
    last_fetch = [0.0 for _ in screens]

    matrix = display.init_matrix()
    canvas = matrix.CreateFrameCanvas()

    print(
        f"Subway sign cycling {len(screens)} screens every {cycle_seconds}s "
        f"(layout: {layout.name}, labels: {labels})."
    )
    if not display.IS_HARDWARE:
        print("Emulator running — open http://localhost:8888 in a browser.")

    frame = 0
    while True:
        now = time.monotonic()

        # Refresh any screen whose data has gone stale (each at its own cadence).
        for i, src in enumerate(sources):
            if now - last_fetch[i] >= refresh_seconds:
                caches[i] = src.fetch(max_results=max_arrivals)
                last_fetch[i] = now

        # Which screen is showing right now.
        idx = (frame // cycle_seconds) % len(screens)
        screen = screens[idx]
        rows = [(a.route, row_text(a, labels), a.minutes_away()) for a in caches[idx]]

        display.draw_station(canvas, screen["name"], rows, layout)
        canvas = matrix.SwapOnVSync(canvas)

        time.sleep(1)
        frame += 1


if __name__ == "__main__":
    main()
