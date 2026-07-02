"""
Milestone A: render a hardcoded station screen (header + 3 rows) to validate the
emulator, layout, fonts, and colors before wiring up live data.

Run:  ./venv/bin/python test_static.py
Then open http://localhost:8888 in a browser.
"""

import time

import display

DUMMY_TITLE = "53 ST  E F"
DUMMY_ARRIVALS = [
    ("F", "Jamaica-179 St", 1),
    ("E", "World Trade Center", 4),
    ("N", "Astoria-Ditmars", 9),
]


def main():
    matrix = display.init_matrix()
    canvas = matrix.CreateFrameCanvas()
    layout = display.Layout(display.DEFAULT_LAYOUT)

    print("Rendering static dummy screen. Open http://localhost:8888")
    while True:
        display.draw_station(canvas, DUMMY_TITLE, DUMMY_ARRIVALS, layout)
        canvas = matrix.SwapOnVSync(canvas)
        time.sleep(1)


if __name__ == "__main__":
    main()
