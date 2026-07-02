"""
Live MTA Bus arrivals (e.g. M15 / M15-SBS) via the MTA Bus Time SIRI API.

Unlike the subway GTFS-Realtime feeds, MTA Bus Time REQUIRES a free API key.
Register at https://register.developer.obanyc.com/ and set it in your env:

    export MTA_BUS_API_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

No secret is stored in the repo. `MTABusArrivals.fetch()` returns the same
`Arrival` objects the display layer expects, so a bus screen renders just like a
subway screen. On any error it serves the last good result.
"""

import datetime
import os
import re

import requests

from mta import Arrival

SIRI_URL = "https://bustime.mta.info/api/siri/stop-monitoring.json"


def _clean_destination(name):
    """
    Tidy a SIRI destination for the tiny display:
    "SELECT BUS SERVICE SOUTH FERRY via 2 AV" -> "South Ferry".
    Drops the redundant SBS prefix and the "via <Av>" suffix, and title-cases
    to match the subway headsigns.
    """
    n = name.strip()
    if n.upper().startswith("SELECT BUS SERVICE "):
        n = n[len("SELECT BUS SERVICE "):]
    n = re.sub(r"\s*-?\s*via .*$", "", n, flags=re.IGNORECASE)
    return n.strip().title()


def _parse_iso(ts):
    """Parse a SIRI ISO-8601 timestamp into a naive local datetime."""
    # e.g. "2026-06-30T15:42:11.000-04:00"
    dt = datetime.datetime.fromisoformat(ts)
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt


class MTABusArrivals:
    def __init__(self, stop_codes, routes=None, api_key=None):
        """
        stop_codes : list of MTA Bus Time stop codes (MonitoringRef), e.g.
                     ["401690"] (one per direction). Find them at
                     https://bustime.mta.info or the stop's bus-stop sign.
        routes     : optional list of route names to keep, e.g. ["M15", "M15+"].
                     `None` keeps every route serving the stop(s).
        api_key    : defaults to the MTA_BUS_API_KEY environment variable.
        """
        self.stop_codes = list(stop_codes)
        self.routes = {r.upper() for r in routes} if routes else None
        self.api_key = api_key or os.environ.get("MTA_BUS_API_KEY")
        self._last_good = []

    def fetch(self, max_results=3):
        if not self.api_key:
            print("[bus] MTA_BUS_API_KEY not set; bus screen has no data.")
            return []
        try:
            arrivals = self._collect()
            self._last_good = arrivals
            return arrivals[:max_results]
        except Exception as exc:
            print(f"[bus] refresh failed ({exc!r}); serving last good result")
            return self._last_good[:max_results]

    def _collect(self):
        results = []
        for stop_code in self.stop_codes:
            results.extend(self._collect_stop(stop_code))
        results.sort(key=lambda a: a.arrival_time)
        return results

    def _collect_stop(self, stop_code):
        params = {
            "key": self.api_key,
            "OperatorRef": "MTA",
            "MonitoringRef": stop_code,
            "version": "2",
        }
        resp = requests.get(SIRI_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        deliveries = (
            data.get("Siri", {})
            .get("ServiceDelivery", {})
            .get("StopMonitoringDelivery", [])
        )
        out = []
        for delivery in deliveries:
            for visit in delivery.get("MonitoredStopVisit", []):
                journey = visit.get("MonitoredVehicleJourney", {})
                raw = (journey.get("PublishedLineName") or [""])[0]
                if self.routes and raw.upper() not in self.routes:
                    continue
                # Short tag for the tiny display: "SBS" for select bus, else the
                # line name (e.g. "M15").
                up = raw.upper()
                route = "SBS" if "SBS" in up or up.endswith("+") else raw
                call = journey.get("MonitoredCall", {})
                eta = call.get("ExpectedArrivalTime") or call.get("AimedArrivalTime")
                if not eta:
                    continue
                destination = _clean_destination((journey.get("DestinationName") or [""])[0])
                direction = journey.get("DirectionRef", "")
                out.append(Arrival(route, destination, _parse_iso(eta), direction))
        return out
