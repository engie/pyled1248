import asyncio
import sys
from enum import Enum
import logging
from .image import text_payload
from .ble import BLEConnection

class SCROLL_TYPE(Enum):
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
        logging.debug("Received:" + payload.hex())
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
        logging.error(f"Failed to decode received data {data.hex()}", exc_info=ex)

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

async def send_text(connection, text, color):
    await send_stream(
        connection,
        PACKET_TYPE.TEXT,
        text_payload(text, color, 16),
    )

if __name__ == "__main__":
    UUID = "2BD223FA-4899-1F14-EC86-ED061D67B468"
    async def spam_display(text):
        async with BLEConnection(UUID, handle_rx) as connection:
            try:
                await scroll(connection, SCROLL_TYPE.SCROLLLEFT)
                await send_text(
                    connection,
                    text,
                    "red",
                )
            except Exception as ex:
                logging.error("Error in BT sending coroutine: ", exc_info=ex)

    logging.basicConfig(
        format="%(asctime)s %(levelname)s: %(message)s", level=logging.DEBUG
    )
    try:
        asyncio.run(spam_display(sys.argv[1]))
    except asyncio.CancelledError:
        pass
