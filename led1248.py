import asyncio
import sys
from enum import Enum
from bleak import BleakScanner, BleakClient, BleakGATTCharacteristic
import logging
from text import text_payload
logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO)
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

def hexy(b):
    return ' '.join('{:02X}'.format(a) for a in b)

async def search():
    logger.info("scanning for 5 seconds, please wait...")

    devices = await BleakScanner.discover(
        return_adv=True, cb=dict(use_bdaddr=False)
    )

    for k, v in devices.items():
        d, a = v
        logger.info()
        logger.info(k)
        logger.info(d)
        logger.info("-" * len(str(d)))
        logger.info(a)

async def blop():
    UUID = "2BD223FA-4899-1F14-EC86-ED061D67B468"
    device = await BleakScanner.find_device_by_address(UUID)

    if device is None:
        logger.warn(f"UUID {UUID} not found")
        sys.exit(1)

    def handle_disconnect(_: BleakClient):
        logger.info("Device was disconnected, goodbye.")
        # cancelling all tasks effectively ends the program
        for task in asyncio.all_tasks():
            task.cancel()

    def handle_rx(_: BleakGATTCharacteristic, data: bytearray):
        logger.info("received:" + hexy(data))

    async def send(client, char, bytes):
        payload = len(bytes).to_bytes(2, "big") + bytes
        padded = bytearray()
        for b in payload:
            if b == 1 or b == 2 or b == 3:
                padded.append(0x02)
                padded.append(b+4)
            else:
                padded.append(b)

        cmd = b"\x01" + padded + b"\x03"
        logging.info(f"Sending: {hexy(cmd)}")
        await client.write_gatt_char(char, cmd, response=False)
        logging.info("Sent. Sleeping")
        await asyncio.sleep(0.1)
    
    def split_payload(payload):
        LEN = 128
        return [payload[start:start+LEN] for start in range(0, len(payload), LEN)]
    
    def build_packet(payload_size, packet_id, packet):
        return b"".join([
            # 'tis not ours to wonder why
            b"\x00",
            # total payload size
            payload_size.to_bytes(2, "big"),
            # packet id
            packet_id.to_bytes(2, "big"),
            # packet size
            len(packet).to_bytes(1, "big"),
            packet,
        ])
    
    def checksum(packet):
        c = 0
        for x in packet:
            c ^= x
        return c.to_bytes(1, "big")
    
    async def send_stream(client, char, payload):
        packets = [build_packet(len(payload), i, data) for i, data in enumerate(split_payload(payload))]
        for packet in packets:
            await send(
                client,
                char,
                b"".join([
                    # Command - 2 means text apparantly
                    b"\x02",
                    packet,
                    # Remember the checksum
                    checksum(packet),
                ]),
            )

    async with BleakClient(device, disconnected_callback=handle_disconnect) as client:
        logger.info("Bleak connected")
        assert len(client.services.services) == 1, "Found not one service"
        service = list(client.services.services.values())[0]
        assert len(service.characteristics) == 1, "Found not one characteristic"
        char = service.characteristics[0]
        logging.info("Got Char")

        try:
            await client.start_notify(char, handle_rx)

            async def scroll(dir):
                await send(client, char, b"\x06" + dir.value.to_bytes(1, "big"))
            # await scroll(SCROLL.SCROLLLEFT)
            await send_stream(client, char, text_payload("Hello World", "red", 16))
            await asyncio.sleep(1)

            logging.info("Done")
        except Exception as ex:
            print(ex)
            raise ex

if __name__ == "__main__":
    #asyncio.run(search())
    try:
        asyncio.run(blop())
    except asyncio.CancelledError:
        pass