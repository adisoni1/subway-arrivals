"""
Helper to find your station's GTFS stop id for config.json.

Searches the static GTFS stops.txt bundled with `nyct-gtfs` for a station name
and prints the matching parent stop ids. Use the PARENT id (no N/S suffix) as
`station_stop_id` in config.json, and set `direction` to N or S separately.

Usage:
  ./venv/bin/python find_stop.py bedford
  ./venv/bin/python find_stop.py "times sq"
"""

import csv
import os
import sys

import nyct_gtfs

STOPS_TXT = os.path.join(
    os.path.dirname(nyct_gtfs.__file__), "gtfs_static", "stops.txt"
)


def find(query):
    query = query.lower()
    matches = []
    with open(STOPS_TXT, newline="") as f:
        for row in csv.DictReader(f):
            # Parent stops have no N/S suffix (location_type == "1", or empty
            # parent_station). Direction rows (e.g. L08N) point to the parent.
            stop_id = row["stop_id"]
            name = row["stop_name"]
            if query in name.lower() and not stop_id[-1] in ("N", "S"):
                matches.append((stop_id, name))
    return matches


def main():
    if len(sys.argv) < 2:
        print("Usage: python find_stop.py <station name>")
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    matches = find(query)

    if not matches:
        print(f"No stations matching {query!r}.")
        return

    print(f"Stations matching {query!r}:\n")
    print(f"  {'stop_id':<8}  station_name")
    print(f"  {'-'*8}  {'-'*30}")
    for stop_id, name in matches:
        print(f"  {stop_id:<8}  {name}")
    print(
        "\nUse the stop_id above as `station_stop_id` in config.json, and set "
        "`direction` to N or S."
    )


if __name__ == "__main__":
    main()
