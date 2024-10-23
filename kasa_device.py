import kasa
from kasa import Device, Discover

from smart_device import SmartDevice


class KasaDevice(SmartDevice):
    def __init__(self, dev_config):
        self.device = None
        self.dev_config = dev_config
        self.device_name = ""

    async def discover(self, device_ip, username, password):
        try:
            self.device = await Discover.discover_single(device_ip, username=username, password=password)
            self.dev_config = self.device.config.to_dict()
            self.device_name = self.device.alias
            await self.device.update()
            return self
        except kasa.exceptions.KasaException:
            return None

    async def connect(self):
        self.device = await Device.connect(config=Device.Config.from_dict(self.dev_config))
        return self

    async def turn_on(self):
        if not self.device.is_on:
            await self.device.turn_on()
            return True
        else:
            return False

    async def turn_off(self):
        if self.device.is_on:
            await self.device.turn_off()
            return True
        else:
            return False