import time

from config import config
from metro_api_common import MetroApiUtils


class MetroApiTrain:
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
                MetroApiUtils.maybe_retry(attempt, retries, str(e))

    def _fetch_train_predictions(
        self, wifi, station_codes, groups, walking_times, show_incidents
    ) -> list[list[dict], list[dict]]:
        print("Fetching trains...")
        start_time = time.monotonic()
        api_url = config["wmata_api_rail_url"] + ",".join(set(station_codes))
        data = MetroApiUtils.query_api(wifi, api_url)
        print("Received train response from WMATA api...")
        time_buffer = time.monotonic() - start_time
        time_buffer = round(time_buffer / 60) + 1

        incidents = []
        if show_incidents:
            train_colors = set(t["Line"] for t in data["Trains"])
            try:
                incidents = self._fetch_rail_incidents(wifi, train_colors)
            except Exception as e:
                print(f"Error fetching rail incidents: {e}")

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
        api_url = config["wmata_api_rail_incident_url"]
        data = MetroApiUtils.query_api(wifi, api_url)
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
