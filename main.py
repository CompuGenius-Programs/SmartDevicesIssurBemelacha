import asyncio
import json
import logging
import os
from datetime import datetime

import kasa.exceptions
import pytz
from dotenv import load_dotenv
from kasa import Discover, Device
from zmanim.util.geo_location import GeoLocation
from zmanim.zmanim_calendar import ZmanimCalendar

load_dotenv()

username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")

location = os.getenv("LOCATION")
timezone = os.getenv("TIMEZONE")
latitude = float(os.getenv("LATITUDE"))
longitude = float(os.getenv("LONGITUDE"))

location = GeoLocation(location, latitude, longitude, timezone, elevation=15)
calendar = ZmanimCalendar(geo_location=location)

logging.basicConfig(format='%(asctime)s | %(levelname)s | %(message)s', level=logging.INFO,
                    datefmt='%a %b %d - %I:%M:%S %p')


async def connect_devices(devices_ips):
    logging.info(f"Devices IPs: {devices_ips}")
    configs = []

    for device_ip in devices_ips:
        try:
            device = await Discover.discover_single(device_ip, username=username, password=password)
        except kasa.exceptions.KasaException:
            logging.error(f"{device_ip} | Could not connect to device")
            continue
        configs.append(device.config.to_dict())
        await device.update()
        logging.info(f"{device.alias} | Connected to device")

    return configs


async def main():
    while True:
        with open("config.json", "r") as f:
            config = json.load(f)

        now = datetime.now(pytz.timezone(timezone))
        if calendar.is_assur_bemelacha(now) or config["testing"]:
            device_configs = await connect_devices(config["devices_ips"])
            for dev_config in device_configs:
                device = await Device.connect(config=Device.Config.from_dict(dev_config))
                if not device.is_on:
                    await device.turn_on()
                    logging.info(f"{device.alias} | Turned light on")
                else:
                    logging.info(f"{device.alias} | Light is already on")

        sleep_time = config["sleep_time"]
        await asyncio.sleep(sleep_time * 60)


if __name__ == "__main__":
    asyncio.run(main())
