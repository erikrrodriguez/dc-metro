import time
from os import getenv

from config import config


class MetroApiOnFireException(Exception):
    pass


class MetroBusApi:
    def __init__(self):
        pass

    def fetch_bus_predictions(
        self, wifi, bus_stops, walking_times, bus_lines, show_incidents
    ) -> list[dict]:
        if len(walking_times) == 0:
            walking_times = [0] * len(bus_stops)
        bus_combos = list(zip(bus_stops, walking_times))
        bus_lines = set(bus_lines)
        retries = config["metro_api_retries"]

        start_time = time.monotonic()
        found_buses = []
        for bus_stop, walking_time in bus_combos:
            for attempt in range(retries + 1):
                try:
                    found_buses.extend(
                        self._fetch_bus_predictions(
                            wifi, bus_stop, walking_time, bus_lines
                        )
                    )
                    break
                except Exception as e:
                    print(f"Attempt {attempt + 1}/{retries + 1} failed: {e}")
                    if attempt < retries:
                        print("Reattempting in 5 seconds...")
                        time.sleep(5)
        found_buses = sorted(found_buses, key=lambda b: b["int_arrival"])
        print(f"Buses found: {found_buses}")

        bus_routes = set([b["loc"] for b in found_buses])
        incidents = []
        if show_incidents and len(bus_routes) > 0:
            print("Fetching bus incidents...")
            for route in bus_routes:
                for attempt in range(retries + 1):
                    try:
                        incidents.extend(self._fetch_bus_incidents(wifi, route))
                        break
                    except Exception as e:
                        print(f"Attempt {attempt + 1}/{retries + 1} failed: {e}")
                        if attempt < retries:
                            print("Reattempting in 5 seconds...")
                            time.sleep(5)
            incidents = [{"description": i} for i in set(incidents)]
            print(f"Bus incidents found: {incidents}")
        duration = time.monotonic() - start_time
        print(f"Update took: {duration:.2f}s")
        return found_buses, incidents

    def _fetch_bus_predictions(
        self, wifi, bus_stop, walking_time, bus_lines
    ) -> list[dict]:
        print(f"Fetching buses for bus stop {bus_stop}...")
        start_time = time.monotonic()
        try:
            api_key = getenv("wmata_api_key")
            api_url = config["wmata_api_bus_url"] + str(bus_stop)
            with wifi.get(
                api_url, headers={"api_key": api_key}, timeout=30
            ) as response:
                if response.status_code == 200:
                    data = response.json()
                else:
                    raise Exception(f"Server error: {response.status_code}")
        except Exception as e:
            raise Exception(f"Encountered error: {e}")
        print("Received bus response from WMATA api...")
        time_buffer = time.monotonic() - start_time
        time_buffer = int(round(time_buffer / 60)) + 1

        buses = [bus for bus in data["Predictions"]]
        buses = [self._normalize_bus_response(bus, time_buffer) for bus in buses]

        if len(bus_lines) > 0:
            dropped_bus_lines = set(
                [bus["loc"] for bus in buses if bus["loc"] not in bus_lines]
            )
            buses = [bus for bus in buses if bus["loc"] in bus_lines]
            if len(dropped_bus_lines) > 0:
                print(
                    f"Dropped bus lines: {dropped_bus_lines}. Consider adding these to your config page."
                )

        if walking_time > 0:
            filtered_buses = list(
                filter(lambda b: b["int_arrival"] - walking_time >= 0, buses)
            )
            if len(filtered_buses) > 0:
                buses = filtered_buses

        return buses

    def _fetch_bus_incidents(self, wifi, bus_route):
        try:
            api_key = getenv("wmata_api_key")
            api_url = config["wmata_api_bus_incident_url"] + str(bus_route)
            with wifi.get(
                api_url, headers={"api_key": api_key}, timeout=30
            ) as response:
                if response.status_code == 200:
                    data = response.json()
                else:
                    raise Exception(f"Server error: {response.status_code}")
        except Exception as e:
            raise Exception(f"Encountered error: {e}")
        print("Received bus incident response from WMATA api...")
        incidents = [i["Description"] for i in data["BusIncidents"]]
        return incidents

    def _remove_vowels(self, text: str):
        vowels = "aeiouAEIOU"
        return "".join(
            [
                char
                for i, char in enumerate(text)
                if char not in vowels or i == 0 or text[i - 1] == " "
            ]
        )

    def _normalize_bus_response(self, bus: dict, buff: int):
        dest = f"{bus['RouteID']} - {bus['DirectionText'].split(' ')[0][0]}"  # C51-N
        # dest = f"{bus['RouteID']}-{bus['DirectionText'].split(" ")[0]}" # C51-North
        # dest = self._remove_vowels(f"{bus['DirectionText'].split(" to ")[1].strip()}") # Tnlytwn

        arrival = str(bus["Minutes"])
        if arrival.isdigit():
            int_arrival = int(arrival)
        else:
            int_arrival = 100
        ret = {
            "line_color": 0x000000,
            "destination": dest,
            "text_arrival": arrival,
            "int_arrival": int_arrival,
            "loc": bus["RouteID"].strip(),
        }
        return ret
