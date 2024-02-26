from PIL import Image, ImageDraw, ImageFont, ImageColor
import os

def get_font_path():
    dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(dir, "spleen-8x16.pil")

def render_text(text, color, height):
    img = Image.new("RGB", (400, 16))
    ImageDraw.Draw(img).text(
        (0, 0),
        text,
        ImageColor.getrgb(color),
        font = ImageFont.load(get_font_path())
    )
    x, y, full_width, full_height = img.getbbox()
    return img.crop((x, 0, full_width, 16))

if __name__ == "__main__":
    import sys
    im = render_text(sys.argv[1], "green", 16)
    im.show()