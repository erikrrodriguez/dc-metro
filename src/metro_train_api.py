import time
from os import getenv

from config import config


class MetroApiOnFireException(Exception):
    pass


class MetroTrainApi:
    LINE_COLORS = {
        "RD": 0xFF0000,
        "OR": 0xFF5500,
        "YL": 0xFFFF00,
        "GR": 0x00FF00,
        "BL": 0x0000FF,
        "SV": 0xAAAAAA,
        "PL": 0xFF00FF,
    }
    DEFAULT_COLOR = 0xFFFFFF

    def __init__(self):
        pass

    def fetch_train_predictions(
        self, wifi, station_codes, groups, walking_times, show_incidents
    ) -> list[list[dict], list[dict]]:
        retries = config["metro_api_retries"]
        for attempt in range(retries + 1):
            try:
                return self._fetch_train_predictions(
                    wifi, station_codes, groups, walking_times, show_incidents
                )
            except Exception as e:
                print(f"Attempt {attempt + 1}/{retries + 1} failed: {e}")
                if attempt < retries:
                    print("Reattempting in 10 seconds...")
                    time.sleep(10)
                else:
                    print("Max retries reached.")
                    raise MetroApiOnFireException()

    def _fetch_train_predictions(
        self, wifi, station_codes, groups, walking_times, show_incidents
    ) -> list[list[dict], list[dict]]:
        print("Fetching trains...")
        start_time = time.monotonic()
        try:
            api_key = getenv("wmata_api_key")
            api_url = config["wmata_api_rail_url"] + ",".join(set(station_codes))
            with wifi.get(
                api_url, headers={"api_key": api_key}, timeout=30
            ) as response:
                if response.status_code == 200:
                    data = response.json()
                else:
                    raise Exception(f"Server error: {response.status_code}")
        except Exception as e:
            raise Exception(f"Encountered error: {e}")
        print("Received train response from WMATA api...")
        time_buffer = time.monotonic() - start_time
        time_buffer = round(time_buffer / 60) + 1

        incidents = []
        if show_incidents:
            train_colors = set(t["Line"] for t in data["Trains"])
            incidents = self._fetch_rail_incidents(wifi, train_colors)

        station_train_groups = dict(zip(station_codes, groups))
        trains = list(
            filter(
                lambda t: (
                    t["LocationCode"] in station_train_groups
                    and t["Group"] in station_train_groups[t["LocationCode"]]
                ),
                data["Trains"],
            )
        )
        trains = [self._normalize_train_response(t, time_buffer) for t in trains]
        trains = [
            t for t in trains if t["line_color"] != self.DEFAULT_COLOR
        ]  # Filter out No Passenger trains

        if max(walking_times) > 0:
            station_walking_times = dict(zip(station_codes, walking_times))
            filtered_trains = list(
                filter(
                    lambda t: t["int_arrival"] - station_walking_times[t["loc"]] >= 0,
                    trains,
                )
            )
            if len(filtered_trains) > 0:
                trains = filtered_trains

        trains = sorted(trains, key=lambda t: t["int_arrival"])

        duration = time.monotonic() - start_time
        print(f"Trains found: {trains}")
        print(f"Update took: {duration:.2f}s")

        return trains, incidents

    def _fetch_rail_incidents(self, wifi, train_colors) -> list:
        print("Fetching rail incidents...")
        try:
            api_key = getenv("wmata_api_key")
            api_url = config["wmata_api_rail_incident_url"]
            with wifi.get(
                api_url, headers={"api_key": api_key}, timeout=30
            ) as response:
                if response.status_code == 200:
                    data = response.json()
                else:
                    raise Exception(f"Server error: {response.status_code}")
        except Exception as e:
            raise Exception(f"Encountered error: {e}")
        print("Received rail incident response from WMATA api...")

        filtered_incidents = []
        for i in data["Incidents"]:
            lines_affected = i["LinesAffected"]  # is a string like "RD; GR; BL;"
            lines_affected = set(
                lines_affected.replace(";", " ").split()
            )  # now like ('RD', 'GR', 'BL')
            if not lines_affected.isdisjoint(train_colors):
                filtered_incidents.append(i)
        filtered_incidents = [
            {"description": i["Description"]} for i in filtered_incidents
        ]
        print(f"Rail incidents found: {filtered_incidents}")
        return filtered_incidents

    def _train_arrival_map(self, arrival_time) -> int:
        if arrival_time == "BRD":
            return 0
        elif arrival_time == "ARR":
            return 1
        elif arrival_time.isdigit():
            return int(float((arrival_time.strip())))
        else:
            return 100  # DLY would fall into this case, but not sure how to handle it without storing what the previous time was

    def _normalize_train_response(self, train: dict, buff: int) -> dict:
        line = train["Line"]
        destination = train["Destination"]
        loc = train["LocationCode"]

        arrival = train["Min"]

        int_arrival = self._train_arrival_map(arrival)

        if arrival.isdigit():
            arrival = int(float((arrival.strip()))) - buff
            if arrival <= 0:
                arrival = "ARR"
            else:
                arrival = str(arrival)

        # Map destination names
        if destination in config.get("station_mapping", {}):
            destination = config["station_mapping"][destination]

        return {
            "line_color": self.LINE_COLORS.get(line, self.DEFAULT_COLOR),
            "line_color_text": line,
            "destination": destination[: config.get("destination_max_characters", 10)],
            "text_arrival": arrival,
            "int_arrival": int_arrival,
            "loc": loc,
        }

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
