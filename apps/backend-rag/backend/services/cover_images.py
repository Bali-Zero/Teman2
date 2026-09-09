"""Canonical rendering helpers for public news cover images."""

from io import BytesIO

from PIL import Image


def _cover_as_jpeg(image_bytes: bytes) -> bytes:
    """Decode an image and return an RGB JPEG without changing its dimensions."""
    with Image.open(BytesIO(image_bytes)) as image:
        rgb_image = image.convert("RGB")
        output = BytesIO()
        rgb_image.save(output, format="JPEG", quality=90, optimize=True)
    return output.getvalue()


def cover_card_as_jpeg(hero_image_bytes: bytes) -> bytes:
    """Return a centre-cropped 16:10 JPEG card derived from a hero image."""
    with Image.open(BytesIO(hero_image_bytes)) as image:
        rgb_image = image.convert("RGB")
        width, height = rgb_image.size
        target_ratio = 16 / 10
        source_ratio = width / height

        if source_ratio > target_ratio:
            crop_width = int(height * target_ratio)
            left = (width - crop_width) // 2
            crop_box = (left, 0, left + crop_width, height)
        else:
            crop_height = int(width / target_ratio)
            top = (height - crop_height) // 2
            crop_box = (0, top, width, top + crop_height)

        card_image = rgb_image.crop(crop_box)
        output = BytesIO()
        card_image.save(output, format="JPEG", quality=90, optimize=True)
    return output.getvalue()
