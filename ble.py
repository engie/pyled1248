import asyncio
from bleak import BleakScanner, BleakClient, BleakGATTCharacteristic
import logging

class BLEConnection:
    def __init__(self, uuid, rx_callback):
        self.uuid = uuid
        self.rx_callback = rx_callback

    async def __aenter__(self):
        self.device = await BleakScanner.find_device_by_address(self.uuid)
        assert self.device != None, f"UUID {self.uuid} not found"

        self.client = BleakClient(
            self.device, disconnected_callback=self.handle_disconnect
        )
        # Apparantly this is how you nest ContextManagers. A bit weird.
        await self.client.__aenter__()

        logging.info(f"Bleak connected to {self.device.address}")
        assert len(self.client.services.services) == 1, "Found not one service"
        service = list(self.client.services.services.values())[0]
        assert len(service.characteristics) == 1, "Found not one characteristic"
        self.char = service.characteristics[0]
        await self.client.start_notify(self.char, self.handle_rx)
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        # Apparantly this is how you nest ContextManagers. A bit weird.
        await self.client.__aexit__(exc_type, exc_value, traceback)

    async def send_packet(self, cmd):
        logging.debug("Sending: " + cmd.hex())
        await self.client.write_gatt_char(self.char, cmd, response=False)
        # Removing this doesn't work at all. Could wait for ACKs,
        # but they seem to take 100-200ms to return from eyeballing logs.
        # This is probably alright for now.
        # TODO: Lift actual packet sending out to a separate task so this
        # doesn't block useful stuff
        await asyncio.sleep(0.1)

    def handle_rx(self, BleakGATTCharacteristic, data: bytearray):
        assert self.rx_callback != None, "No Rx Callback"
        self.rx_callback(data)

    def handle_disconnect(self, _: BleakClient):
        logging.info("BLE Device was disconnected, goodbye.")
        # cancelling all tasks effectively ends the program
        for task in asyncio.all_tasks():
            task.cancel()

# Used manually during device exploration
# TODO: Should this be usable? What API?
async def search():
    logging.info("scanning for 5 seconds, please wait...")
    devices = await BleakScanner.discover(return_adv=True, cb=dict(use_bdaddr=False))
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