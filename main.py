import asyncio
import logging
import os
from datetime import datetime

import pytz
from dotenv import load_dotenv
from kasa import Discover, Device
from zmanim.util.geo_location import GeoLocation
from zmanim.zmanim_calendar import ZmanimCalendar

load_dotenv()

device_ip = os.getenv("DEVICE_IP")
username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")

location = os.getenv("LOCATION")
timezone = os.getenv("TIMEZONE")
latitude = float(os.getenv("LATITUDE"))
longitude = float(os.getenv("LONGITUDE"))

location = GeoLocation(location, latitude, longitude, timezone, elevation=15)
calendar = ZmanimCalendar(geo_location=location)

sleep_mins = 30
logging.basicConfig(format='%(asctime)s | %(levelname)s | %(message)s', level=logging.INFO,
                    datefmt='%a %b %d - %I:%M %p')


async def main():
    device = await Discover.discover_single(device_ip, username=username, password=password)
    config_dict = device.config.to_dict()
    await device.update()
    logging.info(f"Connected to device: {device.alias}")

    while True:
        now = datetime.now(pytz.timezone(timezone))
        if calendar.is_assur_bemelacha(now):
            dev = await Device.connect(config=Device.Config.from_dict(config_dict))
            if not dev.is_on:
                await dev.turn_on()
                logging.info("Turned light on.")
            else:
                logging.info("Light is already on.")

        await asyncio.sleep(60 * sleep_mins)


if __name__ == "__main__":
    asyncio.run(main())
