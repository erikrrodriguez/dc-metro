import time
from os import getenv
from config import config


class MetroApiOnFireException(Exception):
    pass


class MetroApiUtils:
    @staticmethod
    def maybe_retry(attempt, max_retries, error_msg):
        refresh_interval = config["refresh_interval"] * attempt
        print(f"Attempt {attempt + 1}/{max_retries + 1} failed: {error_msg}")
        if attempt < max_retries:
            print(f"Reattempting in {refresh_interval} seconds...")
            time.sleep(refresh_interval)
        else:
            print("Max retries reached.")
            raise MetroApiOnFireException()

    @staticmethod
    def query_api(wifi, api_url):
        api_key = getenv("wmata_api_key")
        try:
            with wifi.get(api_url, headers={"api_key": api_key}, timeout=30) as response:
                if response.status_code == 200:
                    return response.json()
                raise Exception(f"Server error: {response.status_code}")         
        except Exception as e:
            raise Exception(f"Network/Wifi error: {e}")