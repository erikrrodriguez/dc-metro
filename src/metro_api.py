import time
from os import getenv
import json

from config import config

class MetroApiOnFireException(Exception):
    pass

class MetroApi:
    LINE_COLORS = {
        'RD': 0xFF0000,
        'OR': 0xFF5500,
        'YL': 0xFFFF00,
        'GR': 0x00FF00,
        'BL': 0x0000FF,
        'SV': 0xAAAAAA,
        'PL': 0xFF00FF,
    }
    DEFAULT_COLOR = 0xFFFFFF

    def __init__(self):
        pass
    
    def fetch_bus_predictions(self, wifi, bus_stop, bus_walking_time) -> list[dict]:
        retries = config['metro_api_retries']
        for attempt in range(retries + 1):
            try:
                return self._fetch_bus_predictions(wifi, bus_stop, bus_walking_time)
            except Exception as e:
                print(f"Attempt {attempt+1}/{retries+1} failed: {e}")
                if attempt < retries:
                    print('Reattempting in 10 seconds...')
                    time.sleep(10)
                else:
                    print("Max retries reached.")
                    raise MetroApiOnFireException()
    
    def _fetch_bus_predictions(self, wifi, bus_stop, bus_walking_time) -> list[dict]:
        print('Fetching Buses...')
        start_time = time.monotonic()
        try:
            api_key = getenv('wmata_api_key')
            api_url = config['wmata_api_bus_url'] + str(bus_stop)
            response = wifi.get(api_url, headers={'api_key': api_key}, timeout=30)
            if response.status_code == 200:
                try:
                    data = json.loads(response.text)
                except Exception as e:
                    print("Received invalid JSON format. Raw response: ", response.text)
                    raise e
            else:
                raise Exception(f"Server returned error code: {response.status_code}")
            response.close()
        except Exception as e:
            print(f"Encoutered error: {e}")
            raise e
        print('Received bus response from WMATA api...')
        duration = time.monotonic() - start_time
        time_buffer = round(duration / 60) + 1
        
        buses = [bus for bus in data['Predictions']]
        buses = [self._normalize_bus_response(bus, time_buffer) for bus in buses]
        
        if bus_walking_time > 0:
            filtered_buses = list(filter(lambda t: t['int_arrival']-bus_walking_time >= 0, buses))
            if len(filtered_buses) > 0:
                buses = filtered_buses

        print(f"Buses found: {buses}")
        print(f"Update took: {duration:.2f}s")

        return buses

    def _normalize_bus_response(self, bus: dict, buff: int):
        dest = f"{bus['RouteID']} - {bus['DirectionText'].split(" ")[0][0]}" # C51-N
        # dest = f"{bus['RouteID']}-{bus['DirectionText'].split(" ")[0]}" # C51-North
        # dest = f"{bus['DirectionText'].split(" ")[-1]}" # Tenleytown
        ret = {
            'line_color': 0x000000,
            'destination': dest[:config['destination_max_characters']],
            'text_arrival': str(bus['Minutes']),
            'int_arrival': int(bus['Minutes']),
            'loc': bus['RouteID']
        }
        return ret

    def fetch_train_predictions(self, wifi, station_codes, groups, train_walking_times) -> list[list[dict], list[dict]]:
        retries = config['metro_api_retries']
        for attempt in range(retries + 1):
            try:
                return self._fetch_train_predictions(wifi, station_codes, groups, train_walking_times)
            except Exception as e:
                print(f"Attempt {attempt+1}/{retries+1} failed: {e}")
                if attempt < retries:
                    print('Reattempting in 10 seconds...')
                    time.sleep(10)
                else:
                    print("Max retries reached.")
                    raise MetroApiOnFireException()

    def _fetch_train_predictions(self, wifi, station_codes, groups, train_walking_times) -> list[list[dict], list[dict]]:
        print('Fetching Trains...')
        start_time = time.monotonic()
        try:
            api_key = getenv('wmata_api_key')
            api_url = config['wmata_api_rail_url'] + ','.join(set(station_codes))
            response = wifi.get(api_url, headers={'api_key': api_key}, timeout=30)
            if response.status_code == 200:
                try:
                    data = json.loads(response.text)
                except Exception as e:
                    print("Received invalid JSON format. Raw response: ", response.text)
                    raise e
            else:
                raise Exception(f"Server returned error code: {response.status_code}")
            response.close()
        except Exception as e:
            print(f"Encoutered error: {e}")
            raise e
        print('Received train response from WMATA api...')
        duration = time.monotonic() - start_time
        time_buffer = round(duration / 60) + 1
        
        trains = list(filter(lambda t: (t['LocationCode'], t['Group']) in groups, data['Trains']))
        trains = [self._normalize_train_response(t, time_buffer) for t in trains]
        trains = [t for t in trains if t['line_color'] != 0] # Filter out No Passenger trains 

        incidents = None
        if config['show_incidents']:
            train_colors = set(t['line_color_text'] for t in trains)
            incidents = self._fetch_incidents(wifi, train_colors)
        
        if train_walking_times != {}:
            filtered_trains = list(filter(lambda t: t['int_arrival']-train_walking_times[t['loc']] >= 0, trains))
            if len(filtered_trains) > 0:
                trains = filtered_trains
        
        if len(groups) > 1:
            trains = sorted(trains, key=lambda t: t['int_arrival'])

        print(f"Trains found: {trains}")
        print(f"Update took: {duration:.2f}s")

        return trains, incidents
    
    def _fetch_incidents(self, wifi, train_colors):
        print('Fetching Incidents...')
        start_time = time.monotonic()
        try:
            api_key = getenv('wmata_api_key')
            api_url = config['wmata_api_incident_url']
            response = wifi.get(api_url, headers={'api_key': api_key}, timeout=30)
            if response.status_code == 200:
                try:
                    data = json.loads(response.text)
                except Exception as e:
                    print("Received invalid JSON format. Raw response: ", response.text)
                    raise e
            else:
                raise Exception(f"Server returned error code: {response.status_code}")
            response.close()
        except Exception as e:
            print(f"Encoutered error: {e}")
            raise e
        print('Received incident response from WMATA api...')
        duration = time.monotonic() - start_time

        filtered_incidents = []
        for i in data['Incidents']:
            lines_affected = i['LinesAffected'] # is a string like "RD; GR; BL;"
            lines_affected = set(lines_affected.replace(';', ' ').split()) # now like ('RD', 'GR', 'BL')
            if not lines_affected.isdisjoint(train_colors):
                filtered_incidents.append(i)
        print(f"Incidents found: {filtered_incidents}")
        print(f"Update took: {duration:.2f}s")

        filtered_incidents = [{'description': i['Description']} for i in filtered_incidents]
        return filtered_incidents

    def _arrival_map(self, arrival_time) -> int:
        if arrival_time == 'BRD':
            return 0
        elif arrival_time == 'ARR':
            return 1
        elif arrival_time.isdigit():
            return int(float((arrival_time.strip())))
        else:
            return 100 # DLY would fall into this case, but not sure how to handle it without storing what the previous time was

    def _normalize_train_response(self, train: dict, buff:int) -> dict:
        line = train['Line']
        destination = train['Destination']
        loc = train['LocationCode']

        arrival = train["Min"]
        
        int_arrival = self._arrival_map(arrival)
        
        if arrival.isdigit():
            arrival = int(float((arrival.strip()))) - buff
            if arrival <= 0:
                arrival = 'ARR'
            else:
                arrival = str(arrival)
        
        # Map destination names
        if destination in config.get("station_mapping", {}):
            destination = config["station_mapping"][destination]

        return {
            'line_color': self.LINE_COLORS.get(line, self.DEFAULT_COLOR),
            'line_color_text': line,
            'destination': destination[:config.get('destination_max_characters', 10)],
            'text_arrival': arrival,
            'int_arrival': int_arrival,
            'loc': loc
        }