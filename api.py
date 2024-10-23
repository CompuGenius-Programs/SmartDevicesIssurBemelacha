import json
import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from kasa import Discover

load_dotenv()

username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")

app = FastAPI()


async def get_device_by_name(device_name: str):
    with open("config.json", "r") as f:
        config = json.load(f)

    for device_config in config["devices"]:
        if device_config["name"] == device_name:
            try:
                device = await Discover.discover_single(device_config["ip"], username=username, password=password)
                return device
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Could not connect to device: {str(e)}")
    raise HTTPException(status_code=404, detail="Device not found")


@app.get("/toggle_device")
async def toggle_device(device_name: str = Query(..., description="Name of the device to toggle")):
    device = await get_device_by_name(device_name)
    await device.update()
    if device.is_on:
        await device.turn_off()
        return {"status": "off", "message": f"{device.alias} turned off"}
    else:
        await device.turn_on()
        return {"status": "on", "message": f"{device.alias} turned on"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
