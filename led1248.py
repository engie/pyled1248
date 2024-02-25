import asyncio
import sys
from enum import Enum
from bleak import BleakScanner, BleakClient, BleakGATTCharacteristic
import logging
from text import text_payload

logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=logging.INFO)
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

class GRAPHIC_TYPE(Enum):
    TEXT = 2


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


async def blop():
    UUID = "2BD223FA-4899-1F14-EC86-ED061D67B468"
    device = await BleakScanner.find_device_by_address(UUID)

    if device is None:
        logger.error(f"UUID {UUID} not found")
        sys.exit(1)

    def handle_disconnect(_: BleakClient):
        logger.info("Device was disconnected, goodbye.")
        # cancelling all tasks effectively ends the program
        for task in asyncio.all_tasks():
            task.cancel()
    
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
                payload.append(data[i+1] - 4)
                i += 2
            else:
                payload.append(data[i])
                i += 1
        return payload

    def handle_rx(_: BleakGATTCharacteristic, data: bytearray):
        try:
            assert data[0] == 0x01, "Invalid start byte"
            assert data[-1] == 0x03, "Invalid end byte"
            packet = unpad(data[1:-1])
            length = int.from_bytes(packet[:2], "big")
            payload = packet[2:]
            assert len(payload) == length, "Receive size mismatch"
            logger.debug("Received:" + payload.hex())
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

    async def send(client, char, bytes):
        payload = len(bytes).to_bytes(2, "big") + bytes
        padded = pad(payload)
        cmd = b"\x01" + padded + b"\x03"
        logging.debug(f"Sending: {cmd.hex()}")
        await client.write_gatt_char(char, cmd, response=False)
        await asyncio.sleep(0.1)

    def split_payload(payload):
        LEN = 128
        return [payload[start : start + LEN] for start in range(0, len(payload), LEN)]

    def build_packet(payload_size, packet_id, packet):
        return b"".join(
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

    async def send_stream(client, char, stream_type, payload):
        packets = [
            build_packet(len(payload), i, data)
            for i, data in enumerate(split_payload(payload))
        ]
        for packet in packets:
            await send(
                client,
                char,
                b"".join(
                    [
                        stream_type.value.to_bytes(1, "big"),
                        packet,
                        # Remember the checksum
                        checksum(packet),
                    ]
                ),
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

            await scroll(SCROLL.SCROLLLEFT)
            await send_stream(client, char, GRAPHIC_TYPE.TEXT, text_payload("Hello World", "purple", 16))
            await asyncio.sleep(1)

            logging.info("Done")
        except Exception as ex:
            print(ex)
            raise ex


if __name__ == "__main__":
    # asyncio.run(search())
    try:
        asyncio.run(blop())
    except asyncio.CancelledError:
        pass
