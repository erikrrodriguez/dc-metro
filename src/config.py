from adafruit_bitmap_font import bitmap_font

config = {
    ###########################################
    # Define Pages for board to cycle through #
    ###########################################
    # The structure of a page looks like
    # {
    #         "trains": {
    #                 "station_codes": ["E01"], # Required. At least one station. List at https://github.com/metro-sign/dc-metro?tab=readme-ov-file#dc-metro-station-codes
    #                 "train_groups": [["1"]], # Required. one list entry per station code. Either ["1"]  to show one direction or ["1", "2"] to show both
    #                 "walking_times": [7], # Optional. One per station code if provided. Will default to 0 if not provided
    #                 "show_incidents": True, # Optional. Will default to False
    #             },
    #         "buses": {
    #                 "bus_stop_codes": [1001368, 1001441], # Required. At least one bus stop
    #                 "walking_times": [2, 3], # Optional. One per bus stop if provided. Will default to 0
    #                 "bus_lines": ['C51', 'C91'], # Optional, as many as you like. Default will show all buses at a stop
    #                 "show_incidents": True, # Optional. Will default to False
    #             }
    # }
    #
    # Neither 'trains' or 'buses' is required (max 1 of each per page) so you can mix and match however you like. Just be wary of the 50,000 daily API request limit
    ###########################################
    "pages": [
        {
            "trains": {
                "station_codes": ["E01"],
                "train_groups": [["1"]],
                "walking_times": [7],
                "show_incidents": True,
                "predict_next_trains": True,
            },
        },
        {
            "trains": {
                "station_codes": ["E01"],
                "train_groups": [["2"]],
                "walking_times": [7],
                "show_incidents": True,
                "predict_next_trains": True,
            },
        },
        {
            "buses": {
                "bus_stop_codes": [1001368, 1001441, 1001293],
                "walking_times": [2, 3, 6],
                "bus_lines": ["C51", "C91", "D40", "D4X"],
                "show_incidents": True,
            },
        },
    ],
    ###############################
    # Metro Configuration - Rail  #
    ###############################
    "wmata_api_rail_url": "http://api.wmata.com/StationPrediction.svc/json/GetPrediction/",
    "wmata_api_rail_incident_url": "http://api.wmata.com/Incidents.svc/json/Incidents",
    "wmata_api_gtfs_rail_incident_url": "https://api.wmata.com/gtfs-metro-alert/rail-gtfs-metro-alerts.json",
    "use_gtfs_rt_for_rail_incidents": True,
    ###############################
    # Metro Configuration - Bus   #
    ###############################
    "wmata_api_bus_url": "http://api.wmata.com/NextBusService.svc/json/jPredictions?StopID=",
    "wmata_api_bus_incident_url": "http://api.wmata.com/Incidents.svc/json/BusIncidents?Route=",
    "wmata_api_gtfs_bus_incident_url": "https://api.wmata.com/gtfs-metro-alert/bus-gtfs-metro-alerts.json",
    "use_gtfs_rt_for_bus_incidents": False,
    ###############################
    # Metro Configuration - Gen   #
    ###############################
    "metro_api_retries": 3,
    "refresh_interval": 12,  # WMATA updates their APIs every 10-20 seconds. Set this proportional to how many pages and API requests you're making (limit 50,000 per 24 hrs)
    "show_all_if_none_walking": True,  # If there are no trains or buses you can get to in time, then show all trains/buses
    # Full station names mapped to abbreviations
    "station_mapping": {
        "Branch Avenue": "Brnch Av",
        "Branch Av": "Brnch Av",
        "Huntington": "Hntingtn",
        "Vienna/Fairfax-GMU": "Vienna",
        "Franconia-Springfield": "Frnconia",
        "New Carrollton": "New Crltn",
        "Greenbelt": "Grnbelt",
        "Largo Town Center": "Largo",
        "Twinbrook": "Twinbrk",
        "Wiehle-Reston East": "Wiehle",
        "No Passenger": "No Passngr",
        "NoPssenger": "No Passngr",
        "ssenger": "No Passngr",
        "LastTrain": "Last",
    },
    #############################
    # Off Hours Configuration   #
    #############################
    # Instructions at https://learn.adafruit.com/adafruit-magtag/getting-the-date-time
    # Time of day to turn board on and off - must be 24 hour format "HH:MM"
    "display_on_time": "07:00",
    "display_off_time": "23:00",
    #########################
    # Display Configuration #
    #########################
    "matrix_width": 64,
    "num_lines": 3,
    "font": bitmap_font.load_font("lib/5x7.bdf"),
    "character_width": 5,
    "character_height": 6,
    "text_padding": 2,
    "text_color": 0xFF7500,
    "scroll_delay": 0.006,
    "loading_destination_text": "Loading",
    "loading_min_text": "---",
    "loading_line_color": 0xFF00FF,  # Something something Purple Line joke
    "heading_text": "LN DEST   MIN",
    "heading_color": 0xFF0000,
    "line_height": 6,
    "line_width": 4,
    "min_label_characters": 3,
    "destination_max_characters": 8,
}
