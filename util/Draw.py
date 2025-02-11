from PIL import Image, ImageDraw


def paste(background: Image, img: Image, pos: tuple[int, int]):
    overlay = Image.new("RGBA", background.size, (0, 0, 0, 0))
    overlay.paste(img, pos)
    return Image.alpha_composite(background, overlay)


def text(background: Image, **kwargs):
    overlay = Image.new("RGBA", background.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.text(**kwargs)
    return Image.alpha_composite(background, overlay)
