import asyncio
import os
from datetime import datetime

import pytz
from dotenv import load_dotenv
from kasa import Discover
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

sleep_mins = 5


async def main():
    dev = await Discover.discover_single(device_ip, username=username, password=password)

    while True:
        now = datetime.now(pytz.timezone(timezone))
        if calendar.is_assur_bemelacha(now):
            await dev.update()
            if not dev.is_on:
                await dev.turn_on()
                print("Light turned on.")
            else:
                print("Light is already on.")

        await asyncio.sleep(60 * sleep_mins)


if __name__ == "__main__":
    asyncio.run(main())
