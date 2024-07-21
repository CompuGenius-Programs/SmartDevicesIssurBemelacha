import asyncio
import json
import logging
import os
from datetime import datetime, timedelta

import aiohttp
import kasa.exceptions
import pytz
from dotenv import load_dotenv
from kasa import Discover, Device
from zmanim.hebrew_calendar.jewish_calendar import JewishCalendar
from zmanim.util.geo_location import GeoLocation
from zmanim.zmanim_calendar import ZmanimCalendar

load_dotenv()

username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")

location = os.getenv("LOCATION")
timezone = os.getenv("TIMEZONE")
latitude = float(os.getenv("LATITUDE"))
longitude = float(os.getenv("LONGITUDE"))

openweathermap_api_key = os.getenv("OPENWEATHERMAP_API_KEY")

location = GeoLocation(location, latitude, longitude, timezone, elevation=15)
calendar = ZmanimCalendar(geo_location=location)

openweathermap = f"https://api.openweathermap.org/data/3.0/onecall?lat={latitude}&lon={longitude}&appid={openweathermap_api_key}"

logging.basicConfig(format='%(asctime)s | %(levelname)s | %(message)s', level=logging.INFO,
                    datefmt='%a %b %d - %I:%M:%S %p')


async def discover_devices():
    with open("config.json", "r") as f:
        config = json.load(f)

    devices_ips = [device["ip"] for device in config["devices"]]
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


async def shabbos_or_yom_tov(now, config, checking_now=True):
    issur_now = calendar.is_assur_bemelacha(now)
    issur_soon = calendar.is_assur_bemelacha(now + timedelta(minutes=config["light_times"]["erev"]))
    issur_earlier = calendar.is_assur_bemelacha(now - timedelta(minutes=config["light_times"]["motzei"]))

    condition = issur_now or issur_soon or issur_earlier
    if checking_now:
        logging.info(f"Currently Shabbos/Yom Tov: {condition} | "
                     f"Issur Now: {issur_now} | Issur Soon: {issur_soon} | Issur Earlier: {issur_earlier}")
    else:
        logging.info(f"Was Shabbos/Yom Tov: {condition}")
    return condition


async def need_light(now, jewish_calendar, config, device_alias):
    if config["always_light"]:
        logging.info(f"{device_alias} | Config | Need light: True")
        return True

    if config.get("cloud_coverage"):
        async with aiohttp.ClientSession() as session:
            async with session.get(openweathermap) as response:
                data = await response.json()
                if response.status != 200:
                    logging.error(f"Failed to get weather data: {data}")
                    return False
                clouds = data["current"]["clouds"]
                too_cloudy = clouds > config["cloud_coverage"]

        if too_cloudy:
            logging.info(f"{device_alias} | Cloud Coverage ({clouds}) | Need light: True")
            return True

    if jewish_calendar.is_tomorrow_assur_bemelacha():
        nightfall = calendar.plag_hamincha() - timedelta(minutes=config["light_times"]["erev"])
    else:
        nightfall = calendar.tzais() - timedelta(minutes=config["light_times"]["night"])
    sunrise = calendar.hanetz() + timedelta(minutes=config["light_times"]["morning"])
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if midnight <= now < sunrise:
        nightfall -= timedelta(days=1)
    elif sunrise <= now:
        sunrise += timedelta(days=1)

    is_night = nightfall < now < sunrise
    logging.info(f"{device_alias} | Need light: {is_night}")
    return is_night


async def turn_on_light(device):
    if not device.is_on:
        await device.turn_on()
        logging.info(f"{device.alias} | Turned light on")
    else:
        logging.info(f"{device.alias} | Light is already on")


async def turn_off_light(device):
    if device.is_on:
        await device.turn_off()
        logging.info(f"{device.alias} | Turned light off")
    else:
        logging.info(f"{device.alias} | Light is already off")


async def handle_light_timers(now, jewish_calendar, config, device_configs):
    try:
        device_configs = await discover_devices()
    except kasa.exceptions.KasaException:
        logging.error("Failed to discover devices")

    if jewish_calendar.is_tomorrow_assur_bemelacha():
        plag_hamincha_time = calendar.plag_hamincha() - timedelta(minutes=config["light_times"]["erev"])
        time_until_plag_hamincha = (plag_hamincha_time - now).total_seconds()

        if 0 <= time_until_plag_hamincha < config["sleep_time"] * 60:
            await asyncio.sleep(time_until_plag_hamincha)
            for dev_config in device_configs:
                device = await Device.connect(config=Device.Config.from_dict(dev_config))
                await turn_on_light(device)

    elif calendar.is_assur_bemelacha(now):
        tzais_time = calendar.tzais() + timedelta(minutes=config["light_times"]["motzei"])
        time_until_tzais = (tzais_time - now).total_seconds()

        if 0 <= time_until_tzais < config["sleep_time"] * 60:
            await asyncio.sleep(time_until_tzais)
            for dev_config in device_configs:
                device = await Device.connect(config=Device.Config.from_dict(dev_config))
                await turn_off_light(device)


async def main():
    device_configs = await discover_devices()

    while True:
        with open("config.json", "r") as f:
            config = json.load(f)

        now = datetime.now(pytz.timezone(timezone))
        jewish_calendar = JewishCalendar(now.date())
        if config["testing"] or await shabbos_or_yom_tov(now, config):
            try:
                device_configs = await discover_devices()
            except kasa.exceptions.KasaException:
                logging.error("Failed to discover devices")

            for dev_config in device_configs:
                device = await Device.connect(config=Device.Config.from_dict(dev_config))
                device_config = config["devices"][device_configs.index(dev_config)]["config"]

                if await need_light(now, jewish_calendar, device_config, device.alias):
                    await turn_on_light(device)
                else:
                    await turn_off_light(device)

        await handle_light_timers(now, jewish_calendar, config, device_configs)

        sleep_time = config["sleep_time"]
        await asyncio.sleep(sleep_time * 60)


if __name__ == "__main__":
    asyncio.run(main())
