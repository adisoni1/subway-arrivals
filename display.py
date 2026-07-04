"""
Display layer for the NYC subway arrivals sign.

The same code runs on a laptop (RGBMatrixEmulator) and on a Raspberry Pi
(rpi-rgb-led-matrix). The ONLY difference is which library is installed: we try
to import the real hardware bindings first and fall back to the emulator. Class
names and method signatures are identical between the two, so nothing else in
the project needs to change to move to the Pi.
"""

import os

try:
    # Real Raspberry Pi hardware (hzeller/rpi-rgb-led-matrix Python bindings).
    from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics

    IS_HARDWARE = True
except ImportError:
    # Laptop: the emulator exposes the exact same API and renders in a browser.
    from RGBMatrixEmulator import RGBMatrix, RGBMatrixOptions, graphics

    IS_HARDWARE = False


# Where the bundled BDF fonts live (alongside this file).
FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

# --- Display geometry -------------------------------------------------------
# Two 64x32 panels chained horizontally -> a 128x32 canvas. This matches the
# real wiring; the emulator derives its 128x32 canvas from the same numbers.
ROWS = 32
COLS = 64
CHAIN_LENGTH = 2
WIDTH = COLS * CHAIN_LENGTH  # 128 (set at runtime by init_matrix / set_chain_length)


def set_chain_length(chain_length):
    """Change how many 64x32 panels are chained (1 for single-panel testing).

    Updates WIDTH so all drawing (right-alignment, truncation, divider) matches.
    """
    global CHAIN_LENGTH, WIDTH
    CHAIN_LENGTH = int(chain_length)
    WIDTH = COLS * CHAIN_LENGTH

# --- Colors -----------------------------------------------------------------
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
DEST_COLOR = (200, 200, 200)   # destination text (soft white)
MIN_COLOR = (255, 255, 255)    # minutes value
HEADER_COLOR = (255, 176, 0)   # station name header (amber)
DIVIDER_COLOR = (40, 40, 40)   # thin line under header

# MTA route -> official bullet color (R, G, B). See subway-sign-plan.md.
ROUTE_COLORS = {
    "1": (0xEE, 0x35, 0x2E), "2": (0xEE, 0x35, 0x2E), "3": (0xEE, 0x35, 0x2E),
    "4": (0x00, 0x93, 0x3C), "5": (0x00, 0x93, 0x3C), "6": (0x00, 0x93, 0x3C),
    "7": (0xB9, 0x33, 0xAD),
    "A": (0x00, 0x39, 0xA6), "C": (0x00, 0x39, 0xA6), "E": (0x00, 0x39, 0xA6),
    "B": (0xFF, 0x63, 0x19), "D": (0xFF, 0x63, 0x19), "F": (0xFF, 0x63, 0x19), "M": (0xFF, 0x63, 0x19),
    "G": (0x6C, 0xBE, 0x45),
    "J": (0x99, 0x66, 0x33), "Z": (0x99, 0x66, 0x33),
    "L": (0xA7, 0xA9, 0xAC),
    "N": (0xFC, 0xCC, 0x0A), "Q": (0xFC, 0xCC, 0x0A), "R": (0xFC, 0xCC, 0x0A), "W": (0xFC, 0xCC, 0x0A),
    "S": (0x80, 0x81, 0x83),
}

# Routes whose bullet is yellow need black text for contrast.
BLACK_TEXT_ROUTES = {"N", "Q", "R", "W"}

# Bus routes get a colored text tag (e.g. "M15", "SBS") instead of a circle,
# since the route name doesn't fit inside a bullet.
BUS_COLORS = {
    "M15": (0, 110, 184),   # local bus blue
    "SBS": (0, 174, 239),   # Select Bus Service cyan
}
BUS_BLACK_TEXT = {"SBS"}    # tags whose color is light -> black text

# Layout — shared header geometry (an amber station header + a divider line).
HEADER_BASELINE = 6       # baseline y for the station-name header
DIVIDER_Y = 7             # thin divider line under the header
HEADER_BLOCK = 8          # vertical px the header + divider occupy when shown
RIGHT_MARGIN = 1          # gap between minutes text and right edge

# Selectable layout presets. Switch via config.json "layout" or `--layout`.
# By default the row count is computed to fill the height, so hiding the header
# (show_header=False) automatically reclaims its space for an extra/bigger row.
# A preset may pin its own "rows" and force "header" on/off.
#   compact: 5x7 text   -> 3 rows with header, 4 without
#   large:   6x10 text  -> 2 rows with header, 3 without
#   jumbo:   7x13 text  -> exactly 2 big rows, no header, filling the screen
LAYOUTS = {
    "compact": {
        "header_font": "5x7.bdf",
        "text_font": "5x7.bdf",
        "bullet_font": "4x6.bdf",
        "bullet_radius": 3,
        "bullet_cx": 4,
    },
    "large": {
        "header_font": "5x7.bdf",
        "text_font": "6x10.bdf",
        "bullet_font": "5x7.bdf",
        "bullet_radius": 4,
        "bullet_cx": 5,
    },
    "jumbo": {
        "header_font": "5x7.bdf",
        "text_font": "7x13.bdf",
        "bullet_font": "6x10.bdf",
        "bullet_radius": 5,
        "bullet_cx": 6,
        "rows": 2,        # exactly two rows...
        "header": False,  # ...spanning the whole panel (no header)
    },
}
DEFAULT_LAYOUT = "compact"


class Layout:
    """Resolved fonts + geometry for one layout preset."""

    def __init__(self, name=DEFAULT_LAYOUT, show_header=True):
        if name not in LAYOUTS:
            raise ValueError(
                f"Unknown layout {name!r}. Choose from {sorted(LAYOUTS)}."
            )
        cfg = LAYOUTS[name]
        self.name = name
        # A preset may force the header on/off (e.g. jumbo is always full-screen).
        self.show_header = cfg.get("header", show_header)
        self.header_font = load_font(cfg["header_font"])
        self.text_font = load_font(cfg["text_font"])
        self.bullet_font = load_font(cfg["bullet_font"])
        self.bullet_radius = cfg["bullet_radius"]
        self.bullet_cx = cfg["bullet_cx"]

        # Space below the header (or the whole panel if the header is hidden).
        top = HEADER_BLOCK if self.show_header else 0
        avail = ROWS - top
        # Fill the height, unless the preset pins a row count. Never exceed what
        # physically fits.
        fit = max(1, avail // self.text_font.height)
        n = min(cfg["rows"], fit) if "rows" in cfg else fit
        step = avail / n
        self.row_tops = [int(round(top + i * step)) for i in range(n)]
        self.row_height = int(step)

    @property
    def max_rows(self):
        return len(self.row_tops)


def init_matrix(chain_length=None):
    """Create and return an initialized RGBMatrix (hardware or emulator).

    chain_length: number of chained 64x32 panels. Pass 1 to test on a single
    panel (64x32). Defaults to the module value (2 -> 128x32).
    """
    if chain_length is not None:
        set_chain_length(chain_length)
    options = RGBMatrixOptions()
    options.rows = ROWS
    options.cols = COLS
    options.chain_length = CHAIN_LENGTH
    options.parallel = 1
    # Driving the panels through an Adafruit RGB Matrix Bonnet/HAT.
    # If you soldered the bonnet's optional "quality"/E-jumper mod, change this
    # to "adafruit-hat-pwm" to reduce flicker further.
    options.hardware_mapping = "adafruit-hat"
    # The following only matter on real hardware; the emulator ignores them.
    # gpio_slowdown: Pi 3 -> 1-2, Pi 4 -> 3-4. Raise it if you see flicker.
    options.gpio_slowdown = 2
    options.brightness = 100
    options.drop_privileges = False
    return RGBMatrix(options=options)


def load_font(name="5x7.bdf"):
    """Load a bundled BDF font by file name."""
    font = graphics.Font()
    font.LoadFont(os.path.join(FONTS_DIR, name))
    return font


def _color(rgb):
    return graphics.Color(rgb[0], rgb[1], rgb[2])


def _text_width(font, text):
    """Total pixel width a string will occupy in the given font."""
    return sum(font.CharacterWidth(ord(ch)) for ch in text)


def _draw_filled_circle(canvas, cx, cy, radius, rgb):
    """Draw a filled disc (graphics.DrawCircle only draws the perimeter)."""
    r2 = radius * radius
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx * dx + dy * dy <= r2:
                canvas.SetPixel(cx + dx, cy + dy, rgb[0], rgb[1], rgb[2])


def route_color(route):
    """Bullet color for a route id, falling back to gray for unknowns."""
    return ROUTE_COLORS.get(route.upper(), (120, 120, 120))


def _draw_centered_glyph(canvas, font, letter, cx, cy, color):
    """Draw a single glyph centered on (cx, cy).

    Uses only the cross-platform Font API (CharacterWidth / baseline), so it
    behaves identically on the real rgbmatrix library and the emulator. A
    capital/digit occupies roughly the font's ascent (top of glyph down to the
    baseline), so centering that band means placing the text baseline half an
    ascent below the circle center.
    """
    x = cx - _text_width(font, letter) // 2
    baseline = int(round(cy + font.baseline / 2))
    graphics.DrawText(canvas, font, x, baseline, color, letter)


def _draw_subway_bullet(canvas, route, cy, layout):
    """Filled circle + centered route letter. Returns the x where text starts."""
    cx, radius = layout.bullet_cx, layout.bullet_radius
    _draw_filled_circle(canvas, cx, cy, radius, route_color(route))
    letter = route.upper()[:1]
    text_rgb = BLACK if route.upper() in BLACK_TEXT_ROUTES else WHITE
    _draw_centered_glyph(canvas, layout.bullet_font, letter, cx, cy, _color(text_rgb))
    return cx + radius + 3


def _draw_bus_tag(canvas, label, cy, layout):
    """Colored rectangular tag with the route label. Returns text start x."""
    label = label.upper()
    font = layout.bullet_font
    rgb = BUS_COLORS.get(label, (0, 110, 184))
    pad = 1
    w = _text_width(font, label) + 2 * pad
    top = cy - layout.row_height // 2
    for yy in range(top, top + layout.row_height):
        for xx in range(0, w):
            canvas.SetPixel(xx, yy, *rgb)
    text_rgb = BLACK if label in BUS_BLACK_TEXT else WHITE
    graphics.DrawText(canvas, font, pad, cy + font.height // 2 - 1, _color(text_rgb), label)
    return w + 2


def draw_station(canvas, title, arrivals, layout):
    """
    Render one screen with the given `layout`: an amber station/route header,
    then up to `layout.max_rows` arrivals. `arrivals` is a list of
    (route, destination, minutes) tuples. Each row is:
      [route bullet/tag]  destination text ........  N m
    Single-character routes get a subway bullet; multi-character routes (buses
    like "M15"/"SBS") get a colored text tag. Minutes is right-aligned.
    """
    font = layout.text_font
    canvas.Clear()

    # --- Header (optional) ---
    if layout.show_header:
        title = _truncate_to_width(layout.header_font, title, WIDTH - 2)
        graphics.DrawText(canvas, layout.header_font, 1, HEADER_BASELINE, _color(HEADER_COLOR), title)
        for x in range(WIDTH):
            canvas.SetPixel(x, DIVIDER_Y, *DIVIDER_COLOR)

    # --- Arrival rows ---
    for i, (route, destination, minutes) in enumerate(arrivals[: layout.max_rows]):
        cy = layout.row_tops[i] + layout.row_height // 2

        if len(str(route)) <= 1:
            dest_x = _draw_subway_bullet(canvas, route, cy, layout)
        else:
            dest_x = _draw_bus_tag(canvas, route, cy, layout)

        # Minutes, right-aligned.
        mins_text = f"{minutes}m" if isinstance(minutes, int) else str(minutes)
        mw = _text_width(font, mins_text)
        mins_x = WIDTH - mw - RIGHT_MARGIN
        baseline = cy + font.height // 2 - 1
        graphics.DrawText(canvas, font, mins_x, baseline, _color(MIN_COLOR), mins_text)

        # Destination, truncated so it doesn't collide with minutes (keep a gap).
        dest = _truncate_to_width(font, destination, mins_x - dest_x - 3)
        graphics.DrawText(canvas, font, dest_x, baseline, _color(DEST_COLOR), dest)

    return canvas


def _truncate_to_width(font, text, max_width):
    """Trim `text` so it fits within max_width pixels."""
    if _text_width(font, text) <= max_width:
        return text
    while text and _text_width(font, text) > max_width:
        text = text[:-1]
    return text
