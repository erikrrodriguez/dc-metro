from adafruit_bitmap_font import bitmap_font

config = {
	#########################
	# Metro Configuration   #
	#########################
	'wmata_api_rail_url': 'http://api.wmata.com/StationPrediction.svc/json/GetPrediction/',
    'wmata_api_bus_url': 'http://api.wmata.com/NextBusService.svc/json/jPredictions?StopID=',
    'wmata_api_incident_url': 'http://api.wmata.com/Incidents.svc/json/Incidents',
    'metro_api_retries': 3,
	'refresh_interval': 5, # 5 seconds is a good middle ground for updates, as the processor takes its sweet ol time

	#########################
	# Trains			    #
	#########################
    'show_trains': True,
	# Metro Station Codes
    # List is at https://github.com/metro-sign/dc-metro?tab=readme-ov-file#dc-metro-station-codes
	'metro_station_codes': ['E01'],

	# Metro Train Groups, one per station code
	'swap_train_groups': True,
	'train_groups_1': ['1'],
	'train_groups_2': ['2'],

	# Walking Distance Times, ignore trains arriving in less than this time. One per station code
	'train_walking_times': [7],

	# Full names mapped to abbreviations
	'station_mapping': {
		'Branch Avenue': 'Brnch Av',
        'Branch Av': 'Brnch Av',
		'Huntington': 'Hntingtn',
		'Vienna/Fairfax-GMU': 'Vienna',
		'Franconia-Springfield': 'Frnconia',
		'New Carrollton': 'New Crltn',
		'Greenbelt': 'Grnbelt',
		'Huntington': 'Hntingtn',
		'Largo Town Center': 'Largo',
		'Twinbrook': 'Twinbrk',
		'Wiehle-Reston East': 'Wiehle',
		'No Passenger': 'No Passngr',
		'NoPssenger': 'No Passngr',
		'ssenger': 'No Passngr'
	},
    
	#########################
	# Buses			    	#
	#########################
    'show_buses': True,
    'bus_stop_codes': [1001368, 1001441],
    'bus_walking_times': [2, 3],
    
	#########################
	# Incieents			    #
	#########################
    'show_incidents': True,

	#############################
    # Off Hours Configuration   #
    #############################
    # Instructions at https://learn.adafruit.com/adafruit-magtag/getting-the-date-time
    # Time of day to turn board on and off - must be 24 hour format "HH:MM"
    'display_on_time': "07:00",
    'display_off_time': "23:30",

    #########################
    # Display Configuration #
    #########################
	'matrix_width': 64,
	'num_lines': 3,
	'font': bitmap_font.load_font('lib/5x7.bdf'),

	'character_width': 5,
	'character_height': 6,
	'text_padding': 2,
	'text_color': 0xFF7500,
    'scroll_delay': 0.015,

	'loading_destination_text': 'Loading',
	'loading_min_text': '---',
	'loading_line_color': 0xFF00FF, # Something something Purple Line joke

	'heading_text': 'LN DEST   MIN',
	'heading_color': 0xFF0000,

	'line_height': 6,
	'line_width': 4,

	'min_label_characters': 3,
	'destination_max_characters': 8,
}