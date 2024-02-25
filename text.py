from PIL import Image, ImageDraw, ImageFont, ImageColor

def render_text(text, color, height):
    img = Image.new("RGB", (4096, 512))
    ImageDraw.Draw(img).text(
        (0, 0),
        text,
        ImageColor.getrgb(color),
        font=ImageFont.truetype("Keyboard", 72),
    )
    # Scale to a constant height, so calculate the final width
    x, y, full_width, full_height = img.getbbox()
    width = int(full_width * float(height) / full_height)
    return img.resize((width, height), box=img.getbbox())

if __name__ == "__main__":
    im = render_text("Hello World", "green", 16)
    im.show()