from .text import render_text

def band_payload(band_data, width, height):
    # band data is line after line
    # output is an array of bytes, where each byte is a column
    # column has one bit per row, so manually quantising
    # There are assumptions here about the column fitting into 2 bytes (lazy!)
    assert height == 16
    assert len(band_data) == width * height
    out = bytearray()
    for x in range(width):
        col = 0
        for y in range(height):
            col = (col << 1) | int(1 if band_data[y * width + x] > 75 else 0)

        out.append(col >> 8)
        out.append(col & 0xFF)
    return out

def img_payload(im):
    # RGB done separately, in that order, then brought together again one at a time.
    return b"".join(
        [band_payload(im.getdata(x), im.width, im.height) for x in range(3)]
    )

def text_payload(text, color, height):
    im = render_text(text, color, height)
    pixels = img_payload(im)

    # The thing wants the string, for some reason, lets guess it expects old skool encoding
    btxt = text.encode('ascii')
    assert len(btxt) <= 80, "There's a hard limit here. For some reason."

    # Payload seems to be?!
    return b"".join([
        # 24  bytes: zeroes. For reasons?
        bytearray(24),
        # 1 byte: Number of characters in string. The string that isn't used.
        len(btxt).to_bytes(1, "big"),
        # 80 bytes: The string that isn't used.
        btxt,
        # If don't have 80 bytes, then pad out with 0x00.
        bytearray(80-len(btxt)),
        # 2 bytes: Count of pixels, number of bytes used to encode
        len(pixels).to_bytes(2, "big"),
        # N bytes: The encoded pixels
        pixels,
    ])
