"""
Live MTA subway arrivals via the `nyct-gtfs` library (no API key required).

`MTAArrivals.fetch()` returns a sorted list of upcoming arrivals at one station
(optionally both directions) as `Arrival` objects. The display layer recomputes
minutes-from-now from `arrival_time` every second, so the countdown stays smooth
without re-hitting the feed.

If a refresh fails (network/parse error), the last good result is kept so the
sign never blanks or crashes.
"""

import datetime

from nyct_gtfs import NYCTFeed


def normalize_route(route):
    """Collapse express variants onto their base route: 6X->6, FX->F, etc."""
    route = route.upper()
    if len(route) == 2 and route.endswith("X"):
        return route[0]
    return route


class Arrival:
    """One upcoming train at the configured station."""

    __slots__ = ("route", "destination", "arrival_time", "direction")

    def __init__(self, route, destination, arrival_time, direction):
        self.route = route
        self.destination = destination
        self.arrival_time = arrival_time  # naive local datetime
        self.direction = direction        # "N" or "S"

    def minutes_away(self, now=None):
        """Whole minutes from `now` until arrival (floored at 0)."""
        now = now or datetime.datetime.now()
        secs = (self.arrival_time - now).total_seconds()
        return max(0, int(secs // 60))


class MTAArrivals:
    def __init__(self, station_stop_id, direction, routes):
        """
        station_stop_id : GTFS parent stop id WITHOUT direction suffix, e.g. "629".
        direction       : "N", "S", or "both".
        routes          : list of route ids to show, e.g. ["4", "5", "6"].
        """
        self.station_stop_id = station_stop_id
        if str(direction).lower() == "both":
            self.directions = {"N", "S"}
        else:
            self.directions = {direction.upper()}
        self.routes = {normalize_route(r) for r in routes}

        # Group routes by the feed they live in so we fetch each feed once.
        url_map = NYCTFeed._train_to_url
        feeds_needed = {}
        for route in self.routes:
            if route not in url_map:
                raise ValueError(f"Unknown route id: {route}")
            feeds_needed.setdefault(url_map[route], route)

        # One feed per unique URL (don't fetch yet; fetch on first refresh).
        self._feeds = [
            NYCTFeed(route, fetch_immediately=False) for route in feeds_needed.values()
        ]

        self._last_good = []  # cached list[Arrival] from the last successful fetch

    def fetch(self, max_results=3):
        """
        Refresh every feed and return the soonest `max_results` arrivals as a
        list[Arrival], sorted ascending by time. On any error, return the last
        good result instead of raising.
        """
        try:
            arrivals = self._collect()
            self._last_good = arrivals
            return arrivals[:max_results]
        except Exception as exc:  # network, parse, anything -> serve stale data
            print(f"[mta] refresh failed ({exc!r}); serving last good result")
            return self._last_good[:max_results]

    def _collect(self):
        now = datetime.datetime.now()
        results = []

        for feed in self._feeds:
            feed.refresh()
            for trip in feed.trips:
                route = normalize_route(trip.route_id)
                if route not in self.routes:
                    continue
                for stu in trip.stop_time_updates:
                    base = stu.stop_id[:-1]
                    suffix = stu.stop_id[-1]
                    if base != self.station_stop_id or suffix not in self.directions:
                        continue
                    if stu.arrival is None or stu.arrival < now:
                        continue
                    results.append(
                        Arrival(route, trip.headsign_text or "", stu.arrival, suffix)
                    )
                    break  # one stop per trip is enough

        results.sort(key=lambda a: a.arrival_time)
        return results
