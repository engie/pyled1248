import asyncio
import sys
from enum import Enum
from bleak import BleakScanner, BleakClient, BleakGATTCharacteristic
import logging
from image import text_payload

logging.basicConfig(
    format="%(asctime)s %(levelname)s: %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


class SCROLL(Enum):
    SCROLLSTATIC = 1
    SCROLLLEFT = 2
    SCROLLRIGHT = 3
    SCROLLUP = 4
    SCROLLDOWN = 5
    SCROLLSNOWFLAKE = 6
    SCROLLPICTURE = 7
    SCROLLLASER = 8


class PACKET_TYPE(Enum):
    TEXT = 2
    MODE = 6


# Used manually during device exploration
# TODO: Should this be usable? What API?
async def search():
    logger.info("scanning for 5 seconds, please wait...")
    devices = await BleakScanner.discover(return_adv=True, cb=dict(use_bdaddr=False))
    for k, v in devices.items():
        d, a = v
        logger.info()
        logger.info(k)
        logger.info(d)
        logger.info("-" * len(str(d)))
        logger.info(a)


UUID = "2BD223FA-4899-1F14-EC86-ED061D67B468"

async def blop():
    def pad(payload):
        padded = bytearray()
        for b in payload:
            if b == 1 or b == 2 or b == 3:
                padded.append(0x02)
                padded.append(b + 4)
            else:
                padded.append(b)
        return padded

    def unpad(data):
        payload = bytearray()
        i = 0
        while i < len(data):
            if data[i] == 0x02:
                payload.append(data[i + 1] - 4)
                i += 2
            else:
                payload.append(data[i])
                i += 1
        return payload

    def handle_rx(data: bytearray):
        try:
            assert data[0] == 0x01, "Invalid start byte"
            assert data[-1] == 0x03, "Invalid end byte"
            packet = unpad(data[1:-1])
            length = int.from_bytes(packet[:2], "big")
            payload = packet[2:]
            assert len(payload) == length, "Receive size mismatch"
            logger.info("Received:" + payload.hex())
            # No idea what this is
            type = payload[0]
            # Apparantly LEDs can have an ID?
            id = payload[1]
            # Lines up with packet_id in send stream
            packet_id = int.from_bytes(payload[2:4], "big")
            # Should be 0. If not, uhhh, bad?
            status = payload[4]
            assert status == 0x00, "LED reported error"
        except Exception as ex:
            logger.error(f"Failed to decode received data {data.hex()}", exc_info=ex)

    async def send(connection, packet_type, packet):
        wrapped = b"".join(
            [
                (len(packet) + 1).to_bytes(2, "big"),
                packet_type.value.to_bytes(1, "big"),
                packet,
            ]
        )
        cmd = b"".join(
            [
                b"\x01",
                pad(wrapped),
                b"\x03",
            ]
        )
        logging.debug(f"Sending: {cmd.hex()}")
        await connection.send_packet(cmd)

    async def send_stream(connection, packet_type, payload):
        def split_payload(payload):
            LEN = 128
            return [
                payload[start : start + LEN] for start in range(0, len(payload), LEN)
            ]

        def build_packet(payload_size, packet_id, packet):
            contents = b"".join(
                [
                    # 'tis not ours to wonder why
                    b"\x00",
                    # total payload size
                    payload_size.to_bytes(2, "big"),
                    # packet id
                    packet_id.to_bytes(2, "big"),
                    # packet size
                    len(packet).to_bytes(1, "big"),
                    packet,
                ]
            )

            def checksum(packet):
                c = 0
                for x in packet:
                    c ^= x
                return c.to_bytes(1, "big")

            return contents + checksum(contents)

        for i, data in enumerate(split_payload(payload)):
            await send(
                connection,
                packet_type,
                build_packet(len(payload), i, data),
            )

    async def scroll(connection, dir):
        await send(connection, PACKET_TYPE.MODE, dir.value.to_bytes(1, "big"))

    async with BLEConnection(UUID) as connection:
        try:
            connection.set_rx_callback(handle_rx)
            await scroll(connection, SCROLL.SCROLLLEFT)
            await send_stream(
                connection,
                PACKET_TYPE.TEXT,
                text_payload("Hello World", "green", 16),
            )
        except Exception as ex:
            logger.error("Error in BT sending coroutine: ", exc_info=ex)

from typing import Protocol
class Connection(Protocol):
    def set_rx_callback(self, rx_callback) -> None:
        pass

    def send_packet(self, cmd) -> None:
        pass

class BLEConnection:
    def __init__(self, uuid):
        self.uuid = uuid
        self.rx_callback = None

    async def __aenter__(self):
        self.device = await BleakScanner.find_device_by_address(self.uuid)
        assert self.device != None, f"UUID {self.uuid} not found"

        self.client = BleakClient(
            self.device, disconnected_callback=self.handle_disconnect
        )
        # Apparantly this is how you nest ContextManagers. A bit weird.
        await self.client.__aenter__()

        logger.info(f"Bleak connected to {self.device.address}")
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
        logging.info("Sending packet")
        await self.client.write_gatt_char(self.char, cmd, response=False)
        # Removing this doesn't work at all. Could wait for ACKs,
        # but they seem to take 100-200ms to return from eyeballing logs.
        # This is probably alright for now.
        # TODO: Lift actual packet sending out to a separate task so this
        # doesn't block useful stuff
        await asyncio.sleep(0.1)

    def set_rx_callback(self, rx_callback):
        self.rx_callback = rx_callback

    def handle_rx(self, BleakGATTCharacteristic, data: bytearray):
        assert self.rx_callback != None, "No Rx Callback"
        self.rx_callback(data)

    def handle_disconnect(self, _: BleakClient):
        logger.info("BLE Device was disconnected, goodbye.")
        # cancelling all tasks effectively ends the program
        for task in asyncio.all_tasks():
            task.cancel()


if __name__ == "__main__":
    # asyncio.run(search())
    try:
        asyncio.run(blop())
    except asyncio.CancelledError:
        pass
