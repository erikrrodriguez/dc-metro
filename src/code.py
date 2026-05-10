import time
from os import getenv
from config import config
from train_board import TrainBoard
from metro_api import MetroApi, MetroApiOnFireException

import busio
import board
from digitalio import DigitalInOut
import neopixel

# Use these imports for adafruit_esp32spi version 11.0.0 and up.
# Note that frozen libraries may not be up to date.
# import adafruit_esp32spi
# from adafruit_esp32spi.wifimanager import WiFiManager
from adafruit_esp32spi import adafruit_esp32spi
from adafruit_esp32spi.adafruit_esp32spi_wifimanager import WiFiManager

# Connect to Internet
ssid = getenv("CIRCUITPY_WIFI_SSID")
password = getenv("CIRCUITPY_WIFI_PASSWORD")
esp32_cs = DigitalInOut(board.ESP_CS)
esp32_ready = DigitalInOut(board.ESP_BUSY)
esp32_reset = DigitalInOut(board.ESP_RESET)
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)
status_pixel = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.2)
wifi = WiFiManager(esp, ssid, password, status_pixel=status_pixel)

# For telling time, get our username, api key, and desired timezone
aio_username = getenv("aio_username")
aio_key = getenv("aio_key")
location = getenv("timezone")
TIME_URL = f"https://io.adafruit.com/api/v2/{aio_username}/integrations/time/strftime?x-aio-key={aio_key}"
TIME_URL += "&fmt=%25Y-%25m-%25d+%25H%3A%25M%3A%25S.%25L+%25j+%25u+%25z+%25Z"
OFF_HOURS_ENABLED = aio_username and aio_key and config.get("display_on_time") and config.get("display_off_time")

REFRESH_INTERVAL = config['refresh_interval']

# Setup Trains
STATION_CODES = config['metro_station_codes']
TRAIN_GROUPS_1 = list(zip(STATION_CODES, config['train_groups_1']))
TRAIN_GROUPS_2 = list(zip(STATION_CODES, config['train_groups_2'])) if config['swap_train_groups'] else TRAIN_GROUPS_1
train_groups = TRAIN_GROUPS_1
TRAIN_WALKING_TIMES = config['train_walking_times']
if max(TRAIN_WALKING_TIMES) == 0:
    TRAIN_WALKING_TIMES = {}
else:
    TRAIN_WALKING_TIMES = dict(zip(STATION_CODES, TRAIN_WALKING_TIMES))

# Setup Buses
BUS_STOPS = config['bus_stop_codes']
BUS_WALKING_TIMES = config['bus_walking_times']
bus_stop = BUS_STOPS[0]

def is_off_hours() -> bool:
    ON_HOUR, ON_MINUTE = map(int, config['display_on_time'].split(":"))
    OFF_HOUR, OFF_MINUTE = map(int, config['display_off_time'].split(":"))
    try:
        now = wifi.get(TIME_URL, timeout=1).text
        now_hour = int(now[11:13])
        now_minute = int(now[14:16])
        after_end = now_hour > OFF_HOUR or (now_hour == OFF_HOUR and now_minute > OFF_MINUTE)
        before_start = now_hour < ON_HOUR or (now_hour == ON_HOUR and now_minute < ON_MINUTE)

        if ON_HOUR < OFF_HOUR or (ON_HOUR == OFF_HOUR and ON_MINUTE < OFF_MINUTE):
            return after_end or before_start
        else:
            return after_end and before_start
    except Exception as e:
        print(e)
        return False

def refresh_trains(train_groups: list) -> list[list[dict], list[dict]]:
    try:
        trains, incidents = api.fetch_train_predictions(wifi, STATION_CODES, train_groups, TRAIN_WALKING_TIMES)
    except MetroApiOnFireException:
        print('WMATA API might be on fire. Resetting wifi ...')
        esp.reset()
        time.sleep(10)
        wifi.reset()
        return None
    return trains, incidents

def refresh_buses(bus_stop: list) -> [dict]:
    try:
        buses = api.fetch_bus_predictions(wifi, bus_stop, BUS_WALKING_TIMES[BUS_STOPS.index(bus_stop)])
    except MetroApiOnFireException:
        print('WMATA API might be on fire. Resetting wifi ...')
        esp.reset()
        time.sleep(10)
        wifi.reset()
        return None
    return buses

def refresh(train_groups: list, bus_stop: list) -> [dict]:
    trains = None
    buses = None
    incidents = None
    if config['show_trains']:
        trains, incidents = refresh_trains(train_groups)
    if config['show_buses']:
        buses = refresh_buses(bus_stop)
    return {'trains': trains, 'buses': buses, 'incidents': incidents}


api = MetroApi()
train_board = TrainBoard(lambda: refresh(train_groups, bus_stop))

while True:
    start_time = time.monotonic()
    if OFF_HOURS_ENABLED and is_off_hours():
        train_board.turn_off_display()
    else:
        train_board.refresh()
        train_board.turn_on_display()
        if config['swap_train_groups']:
            train_groups = TRAIN_GROUPS_1 if train_groups == TRAIN_GROUPS_2 else TRAIN_GROUPS_2
            bus_stop = BUS_STOPS[1] if bus_stop == BUS_STOPS[0] else BUS_STOPS[0]
    time.sleep(REFRESH_INTERVAL)
    duration = time.monotonic() - start_time
    print(f"Total Update took: {duration:.2f}s")
