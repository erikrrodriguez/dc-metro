import time
import rtc
from os import getenv
from config import config
from train_board import TrainBoard, ErrorBoard
from metro_api_common import MetroApiOnFireException
from metro_api_train import MetroApiTrain
from metro_api_bus import MetroApiBus
import gc

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
REFRESH_INTERVAL = config["refresh_interval"]
LAST_SYNC_TIME = -90000

# For telling time, get our username, api key, and desired timezone
aio_username = getenv("aio_username")
aio_key = getenv("aio_key")
location = getenv("timezone")
OFF_HOURS_ENABLED = (
    aio_username
    and aio_key
    and config.get("display_on_time")
    and config.get("display_off_time")
)


def sync_rtc():
    time_api_url = f"https://io.adafruit.com/api/v2/{aio_username}/integrations/time/strftime?x-aio-key={aio_key}"
    time_api_url += "&fmt=%25Y-%25m-%25d+%25H%3A%25M%3A%25S.%25L+%25j+%25u+%25z+%25Z"
    while True:
        try:
            print("Syncing RTC with API...")
            with wifi.get(time_api_url, timeout=10) as response:
                if response.status_code == 200:
                    now = response.text
                    date_str, time_str, _ = now.split(" ", 2)
                    y, m, d = map(int, date_str.split("-"))
                    hh, mm, ss = map(int, time_str.split(".")[0].split(":"))

                    rtc.RTC().datetime = time.struct_time(
                        (y, m, d, hh, mm, ss, 0, -1, -1)
                    )
                    print("RTC Sync complete.")
                    break
        except Exception as e:
            print(f"Time Sync failed: {e}")
            time.sleep(REFRESH_INTERVAL)


def is_off_hours() -> bool:
    ON_HOUR, ON_MINUTE = map(int, config["display_on_time"].split(":"))
    OFF_HOUR, OFF_MINUTE = map(int, config["display_off_time"].split(":"))

    now = rtc.RTC().datetime
    now_hour = now.tm_hour
    now_minute = now.tm_min

    after_end = now_hour > OFF_HOUR or (
        now_hour == OFF_HOUR and now_minute > OFF_MINUTE
    )
    before_start = now_hour < ON_HOUR or (
        now_hour == ON_HOUR and now_minute < ON_MINUTE
    )

    if ON_HOUR < OFF_HOUR or (ON_HOUR == OFF_HOUR and ON_MINUTE < OFF_MINUTE):
        return after_end or before_start
    else:
        return after_end and before_start


def validate_pages(config):
    if "pages" not in config:
        raise ValueError("config file is missing pages entry")
    pages = config["pages"]
    if len(pages) == 0:
        raise ValueError("pages must have at least one entry in config file")
    for i, page in enumerate(pages):
        trains = page.get("trains", {})
        if trains:
            if type(trains) is not dict:
                raise ValueError(f"Page {i}: Trains entry must be a dictionary")
            if "station_codes" not in trains or "train_groups" not in trains:
                raise ValueError(
                    f"Page {i}: Trains entry must have 'station_codes' and 'train_groups' entries"
                )
            station_codes = trains["station_codes"]
            if type(station_codes) is not list:
                raise ValueError(f"Page {i}: Trains station_codes entry must be a list")
            train_groups = trains["train_groups"]
            if type(train_groups) is not list:
                raise ValueError(f"Page {i}: Trains train_groups entry must be a list")
            walking_times = trains.get("walking_times", [])
            if type(walking_times) is not list:
                raise ValueError(f"Page {i}: Trains walking_times entry must be a list")

            station_count = len(station_codes)
            if len(train_groups) != len(station_codes):
                raise ValueError(
                    f"Page {i} - Trains: Found {len(train_groups)} train_groups, but {station_count} station_codes."
                )
            if len(walking_times) > 0 and len(walking_times) != station_count:
                raise ValueError(
                    f"Page {i} - Trains: Found {len(walking_times)} walking_times, but {station_count} station_codes."
                )

        buses = page.get("buses", {})
        if buses:
            if type(buses) is not dict:
                raise ValueError(f"Page {i}: Buses entry must be a dictionary")
            if "bus_stop_codes" not in buses:
                raise ValueError(
                    f"Page {i}: Buses entry must have 'bus_stop_codes' entry"
                )
            stop_codes = buses["bus_stop_codes"]
            if type(stop_codes) is not list:
                raise ValueError(f"Page {i}: Buses bus_stop_codes entry must be a list")
            walking_times = buses.get("walking_times", [])
            if type(walking_times) is not list:
                raise ValueError(f"Page {i}: Buses walking_times entry must be a list")

            if len(walking_times) > 0 and len(walking_times) != len(stop_codes):
                raise ValueError(
                    f"Page {i} - Buses: Found {len(walking_times)} walking_times, but {len(stop_codes)} bus_stop_codes."
                )
    print("Page validation successful")


def reset_wifi():
    print("WMATA API might be on fire. Resetting wifi ...")
    esp.reset()
    time.sleep(REFRESH_INTERVAL)
    wifi.reset()
    time.sleep(REFRESH_INTERVAL)


def refresh_trains(trains: dict) -> list[list[dict], list[dict]]:
    found_trains = []
    incidents = []
    try:
        found_trains, incidents = train_api.fetch_train_predictions(
            wifi,
            trains["station_codes"],
            trains["train_groups"],
            trains.get("walking_times", []),
            trains.get("show_incidents", False),
            trains.get("predict_next_trains", False)
        )
    except MetroApiOnFireException:
        reset_wifi()
    return found_trains, incidents


def refresh_buses(buses: dict) -> list[dict]:
    found_buses = []
    incidents = []
    try:
        found_buses, incidents = bus_api.fetch_bus_predictions(
            wifi,
            buses["bus_stop_codes"],
            buses.get("walking_times", []),
            buses.get("bus_lines", []),
            buses.get("show_incidents", False),
        )
    except MetroApiOnFireException:
        reset_wifi()
    return found_buses, incidents


def refresh(page: dict) -> list[dict]:
    trains = page.get("trains", {})
    buses = page.get("buses", {})
    found_trains = []
    found_buses = []
    rail_incidents = []
    bus_incidents = []

    if len(trains) > 0:
        found_trains, rail_incidents = refresh_trains(trains)
    if len(buses) > 0:
        found_buses, bus_incidents = refresh_buses(buses)
    incidents = rail_incidents + bus_incidents
    return {
        "trains": found_trains,
        "buses": found_buses,
        "incidents": incidents,
    }


try:
    validate_pages(config)
except Exception as e:
    print(f"Error with page configuration: {e}")
    train_board = ErrorBoard(f"ERROR with config pages! {str(e)}")

try:
    PAGES = config["pages"]
    page_index = 0
    train_api = MetroApiTrain()
    bus_api = MetroApiBus()
    train_board = TrainBoard(lambda: refresh(PAGES[page_index]))
    while True:
        start_time = time.monotonic()
        if OFF_HOURS_ENABLED and (start_time - LAST_SYNC_TIME > 86400):
            sync_rtc()
            LAST_SYNC_TIME = time.monotonic()

        if OFF_HOURS_ENABLED and is_off_hours():
            train_board.turn_off_display()
        else:
            print(f"Fetching page: {page_index + 1}")
            train_board.refresh()
            train_board.turn_on_display()
            page_index = (page_index + 1) % len(PAGES)
        time.sleep(REFRESH_INTERVAL)
        duration = time.monotonic() - start_time
        print(f"===================================Total update took: {duration:.2f}s")
        gc.collect()
except Exception as e:
    print(f"Error: {e}")
    train_board = ErrorBoard(f"ERROR! {str(e)}")
