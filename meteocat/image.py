from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from meteocat.config import settings


def _assemble_tiles(tiles: list[Path], columns: int) -> Image.Image:
    tile_size = settings.tile_size
    images = [Image.open(t) for t in tiles]
    rows = (len(images) + columns - 1) // columns
    width = columns * tile_size
    height = rows * tile_size
    canvas = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    for i, img in enumerate(images):
        col = i % columns
        row = i // columns
        canvas.paste(img, (col * tile_size, row * tile_size))
    return canvas


def _composite_radar(background_path: Path, radar_path: Path, output_path: Path, opacity: float) -> None:
    background = Image.open(background_path).convert('RGBA')
    radar = Image.open(radar_path).convert('RGBA')
    radar = radar.resize(
        (int(background.width * settings.resize_factor), int(background.height * settings.resize_factor)),
        Image.LANCZOS,
    )
    alpha = radar.split()[3]
    alpha = alpha.point(lambda p: int(p * opacity))
    radar.putalpha(alpha)
    background.paste(radar, (settings.paste_offset_x, settings.paste_offset_y), radar)
    background.convert('RGB').save(output_path)


def _apply_background_overlays(img: Image.Image) -> None:
    draw = ImageDraw.Draw(img)
    draw.rectangle(settings.rectangle_coords, fill='#9c9c9c')


def _make_dark_variant(img: Image.Image) -> Image.Image:
    white = Image.new('RGB', img.size, (255, 255, 255))
    white.paste(img.convert('RGBA'), mask=img.split()[3])
    img_dark = ImageOps.invert(white)
    ImageDraw.floodfill(img_dark, settings.floodfill_pos, (41, 41, 41), thresh=settings.floodfill_thresh)
    return img_dark
