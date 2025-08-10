python
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

time_format = "%a %b %d - %I:%M:%S %p"
logging.basicConfig(format='%(asctime)s | %(levelname)s | %(message)s', level=logging.INFO, datefmt=time_format)


async def discover_devices():
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
    except Exception as e:
        logging.error(f"Failed to load config.json: {e}")
        return []

    devices_ips = [device["ip"] for device in config.get("devices", [])]
    logging.info(f"Devices IPs: {devices_ips}")
    configs = []

    for device_ip in devices_ips:
        try:
            device = await Discover.discover_single(device_ip, username=username, password=password)
            configs.append(device.config.to_dict())
            await device.update()
            logging.info(f"{device.alias} | Connected to device")
            if config["devices"][devices_ips.index(device_ip)].get("name"):
                if device.alias != config["devices"][devices_ips.index(device_ip)]["name"]:
                    logging.warning(
                        f"{device.alias} | Device name does not match config - {config['devices'][devices_ips.index(device_ip)]['name']}")
        except kasa.exceptions.KasaException as e:
            logging.error(f"{device_ip} | Could not connect to device: {e}")
        except Exception as e:
            logging.error(f"{device_ip} | Unexpected error: {e}")

    return configs


async def safe_device_connect(dev_config):
    try:
        return await Device.connect(config=Device.Config.from_dict(dev_config))
    except kasa.exceptions.KasaException as e:
        logging.error(f"Failed to connect to device: {e}")
    except Exception as e:
        logging.error(f"Unexpected error during device connect: {e}")
    return None


async def shabbos_or_yom_tov(now, jewish_calendar, config):
    erev_time = calendar.plag_hamincha() - timedelta(minutes=config["light_times"]["erev"])
    motzei_time = calendar.tzais() + timedelta(minutes=config["light_times"]["motzei"])
    condition = (now <= motzei_time and jewish_calendar.is_assur_bemelacha()) or (
            now >= erev_time and jewish_calendar.is_tomorrow_assur_bemelacha())
    logging.info(f"Currently Shabbos/Yom Tov: {condition}")
    return condition


async def need_light(now, jewish_calendar, config, device_config, device_alias):
    if device_config["always_light"]:
        logging.info(f"{device_alias} | Always On: True | Need light: True")
        return True

    if jewish_calendar.is_tomorrow_assur_bemelacha():
        nightfall = calendar.plag_hamincha() - timedelta(minutes=config["light_times"]["erev"])
    else:
        nightfall = calendar.tzais() - timedelta(minutes=device_config["light_times"]["night"])
    sunrise = calendar.hanetz() + timedelta(minutes=device_config["light_times"]["morning"])
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if midnight <= now < sunrise:
        nightfall -= timedelta(days=1)
    elif sunrise <= now:
        sunrise += timedelta(days=1)

    is_night = nightfall < now < sunrise
    if is_night:
        logging.info(
            f"{device_alias} | Nightfall ({nightfall.strftime(time_format)}), Sunrise ({sunrise.strftime(time_format)}) | Need light: True")
        return True

    clouds = 0
    if device_config.get("cloud_coverage"):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(openweathermap) as response:
                    data = await response.json()
                    if response.status != 200:
                        logging.error(f"Failed to get weather data: {data}")
                        return False
                    clouds = data["current"]["clouds"]
                    too_cloudy = clouds > device_config["cloud_coverage"]
        except Exception as e:
            logging.error(f"Error fetching weather data: {e}")
            too_cloudy = False

        if too_cloudy:
            logging.info(f"{device_alias} | Cloud Coverage ({clouds}%) | Need light: True")
            return True

    logging.info(
        f"{device_alias} | Always On: False - Cloud Coverage ({clouds}%) - Nightfall ({nightfall.strftime(time_format)}), Sunrise ({sunrise.strftime(time_format)}) | Need light: False")
    return False


async def turn_on_light(device):
    if device is None:
        logging.warning("Device is None, cannot turn on light")
        return
    try:
        if not device.is_on:
            await device.turn_on()
            logging.info(f"{device.alias} | Turned light on")
        else:
            logging.info(f"{device.alias} | Light is already on")
    except kasa.exceptions.KasaException as e:
        logging.error(f"{getattr(device, 'alias', 'Unknown device')} | Failed to turn on light: {e}")
    except Exception as e:
        logging.error(f"{getattr(device, 'alias', 'Unknown device')} | Unexpected error: {e}")


async def turn_off_light(device):
    if device is None:
        logging.warning("Device is None, cannot turn off light")
        return
    try:
        if device.is_on:
            await device.turn_off()
            logging.info(f"{device.alias} | Turned light off")
        else:
            logging.info(f"{device.alias} | Light is already off")
    except kasa.exceptions.KasaException as e:
        logging.error(f"{getattr(device, 'alias', 'Unknown device')} | Failed to turn off light: {e}")
    except Exception as e:
        logging.error(f"{getattr(device, 'alias', 'Unknown device')} | Unexpected error: {e}")


async def handle_light_timers(now, jewish_calendar, config, device_configs):
    try:
        device_configs = await discover_devices()
    except kasa.exceptions.KasaException as e:
        logging.error(f"Failed to discover devices: {e}")
        device_configs = []

    if jewish_calendar.is_tomorrow_assur_bemelacha():
        plag_hamincha_time = calendar.plag_hamincha() - timedelta(minutes=config["light_times"]["erev"])
        time_until_plag_hamincha = (plag_hamincha_time - now).total_seconds()

        if 0 <= time_until_plag_hamincha < config["sleep_time"] * 60:
            logging.info(f"Sleeping until Plag Hamincha ({plag_hamincha_time.strftime(time_format)})")
            await asyncio.sleep(time_until_plag_hamincha)
            for dev_config in device_configs:
                device = await safe_device_connect(dev_config)
                await turn_on_light(device)

    elif jewish_calendar.is_assur_bemelacha():
        tzais_time = calendar.tzais() + timedelta(minutes=config["light_times"]["motzei"])
        time_until_tzais = (tzais_time - now).total_seconds()

        if 0 <= time_until_tzais < config["sleep_time"] * 60:
            logging.info(f"Sleeping until Tzais ({tzais_time.strftime(time_format)})")
            await asyncio.sleep(time_until_tzais)
            for dev_config in device_configs:
                device = await safe_device_connect(dev_config)
                await turn_off_light(device)


async def main():
    device_configs = await discover_devices()

    while True:
        try:
            with open("config.json", "r") as f:
                config = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load config.json: {e}")
            await asyncio.sleep(60)
            continue

        now = datetime.now(pytz.timezone(timezone))
        calendar.date = now.date()
        jewish_calendar = JewishCalendar(now.date())
        try:
            if config.get("testing") or await shabbos_or_yom_tov(now, jewish_calendar, config):
                try:
                    device_configs = await discover_devices()
                except kasa.exceptions.KasaException as e:
                    logging.error(f"Failed to discover devices: {e}")
                    device_configs = []

                for dev_config in device_configs:
                    device = await safe_device_connect(dev_config)
                    if device is None:
                        continue
                    device_config = config["devices"][device_configs.index(dev_config)]["config"]

                    if await need_light(now, jewish_calendar, config, device_config, getattr(device, "alias", "Unknown device")):
                        await turn_on_light(device)
                    else:
                        await turn_off_light(device)

            await handle_light_timers(now, jewish_calendar, config, device_configs)
        except Exception as e:
            logging.error(f"Unexpected error in main loop: {e}")

        sleep_time = config.get("sleep_time", 1)
        await asyncio.sleep(sleep_time * 60)


if __name__ == "__main__":
    asyncio.run(main())