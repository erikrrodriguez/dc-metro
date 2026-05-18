import time
import gc

from config import config
from metro_api_common import MetroApiUtils


class MetroApiBus:
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
                    MetroApiUtils.maybe_retry(attempt, retries, str(e))
        found_buses = sorted(found_buses, key=lambda b: b["int_arrival"])
        print(f"Buses found: {found_buses}")

        if len(bus_lines) == 0:
            bus_lines = set([b["loc"] for b in found_buses])

        incidents = []
        if show_incidents and len(bus_lines) > 0:
            print("Fetching bus incidents...")
            if config['use_gtfs_rt_for_bus_incidents']:
                try:
                    incidents = self._fetch_bus_incidents_gtfs_rt(wifi, bus_lines)
                except Exception as e:
                    pass
            else:
                for route in bus_lines:
                    for attempt in range(retries + 1):
                        try:
                            incidents.extend(self._fetch_bus_incidents(wifi, route))
                            break
                        except Exception as e:
                            MetroApiUtils.maybe_retry(attempt, retries, str(e))
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
        api_url = config["wmata_api_bus_url"] + str(bus_stop)
        data = MetroApiUtils.query_api(wifi, api_url)
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
            if len(filtered_buses) > 0 or not config["show_all_if_none_walking"]:
                buses = filtered_buses

        return buses

    def _fetch_bus_incidents(self, wifi, bus_route):
        api_url = config["wmata_api_bus_incident_url"] + str(bus_route)
        data = MetroApiUtils.query_api(wifi, api_url)
        print("Received bus incident response from WMATA api...")
        incidents = [i["Description"] for i in data["BusIncidents"]]
        return incidents

    def _fetch_bus_incidents_gtfs_rt(self, wifi, bus_lines):
        api_url = config["wmata_api_gtfs_bus_incident_url"]
        data = MetroApiUtils.query_api(wifi, api_url)
        print("Received bus incident response from WMATA api...")

        filtered_incidents = []
        for incident in data:
            for entity in incident.get("entities", []):
                alert = entity.get("alert", {})
                lines_affected = set()
                for info in alert.get("informedEntities", []):
                    route_id = info.get("routeId")
                    if route_id:
                        lines_affected.add(route_id)

                if not lines_affected.isdisjoint(bus_lines):
                    desc_obj = alert.get("descriptionText", {})
                    translations = desc_obj.get("translations", [])
                    for translation in translations:
                        if translation.get("language", "") == "en":
                            description = translation.get("text", "")
                            description = description.replace("\n", "")
                            filtered_incidents.append({"description": description})
        return filtered_incidents

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
