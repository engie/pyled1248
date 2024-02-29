import asyncio
from bleak import BleakScanner, BleakClient, BleakGATTCharacteristic
import logging

SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"

class BLEConnection:
    def __init__(self, rx_callback):
        self.rx_callback = rx_callback

    async def __aenter__(self):
        def led_test(device, advertisement):
            return SERVICE_UUID in advertisement.service_uuids
        self.device = await BleakScanner.find_device_by_filter(led_test)
        assert self.device != None, f"SERVICE UUID {SERVICE_UUID} not found"

        self.client = BleakClient(
            self.device,
            services = [SERVICE_UUID],
            disconnected_callback=self.handle_disconnect
        )
        # Apparantly this is how you nest ContextManagers. A bit weird.
        await self.client.__aenter__()

        self.char = self.client.services.get_characteristic(CHARACTERISTIC_UUID)
        assert self.char != None, f"Could not find characteristic {CHARACTERISTIC_UUID}"
        await self.client.start_notify(self.char, self.handle_rx)
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        # Apparantly this is how you nest ContextManagers. A bit weird.
        await self.client.__aexit__(exc_type, exc_value, traceback)

    async def send_packet(self, cmd):
        await self.client.write_gatt_char(self.char, cmd, response=False)
        # Removing this doesn't work at all. Could wait for ACKs,
        # but they seem to take 100-200ms to return from eyeballing logs.
        # This is probably alright for now.
        # TODO: Lift actual packet sending out to a separate task so this
        # doesn't block useful stuff
        await asyncio.sleep(0.2)

    def handle_rx(self, BleakGATTCharacteristic, data: bytearray):
        assert self.rx_callback != None, "No Rx Callback"
        self.rx_callback(data)

    def handle_disconnect(self, _: BleakClient):
        logging.debug("BLE Device was disconnected, goodbye.")

# Used manually during device exploration
# TODO: Should this be usable? What API?
async def search():
    logging.info("scanning for 5 seconds, please wait...")
    devices = await BleakScanner.discover(return_adv=True, cb=dict(use_bdaddr=True))
    for k, v in devices.items():
        d, a = v
        logging.info(k)
        logging.info(d)
        logging.info("-" * len(str(d)))
        logging.info(a)

if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s %(levelname)s: %(message)s", level=logging.INFO
    )
    try:
        asyncio.run(search())
    except asyncio.CancelledError:
        pass
