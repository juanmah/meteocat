from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from meteocat.download import _BACKGROUND_ZOOM, _RADAR_ZOOM

_TILE_SIZE = 256

_RADAR_TILE_RANGE_X = range(63, 66)
_RADAR_TILE_RANGE_Y = range(79, 81)
_BACKGROUND_TILE_RANGE_X = range(510, 528)
_BACKGROUND_TILE_RANGE_Y = range(638, 648)

_CROP_LEFT = 300
_CROP_TOP = 300
_CROP_WIDTH = 3840
_CROP_HEIGHT = 2160

_RADAR_SCALE = 2 ** (_BACKGROUND_ZOOM - _RADAR_ZOOM)
_RADAR_SIZE = (
    len(_RADAR_TILE_RANGE_X) * _TILE_SIZE * _RADAR_SCALE,
    len(_RADAR_TILE_RANGE_Y) * _TILE_SIZE * _RADAR_SCALE,
)
_RADAR_PASTE_OFFSET = (
    _RADAR_TILE_RANGE_X.start * _TILE_SIZE * _RADAR_SCALE - _BACKGROUND_TILE_RANGE_X.start * _TILE_SIZE - _CROP_LEFT,
    _BACKGROUND_TILE_RANGE_Y.stop * _TILE_SIZE - _RADAR_TILE_RANGE_Y.stop * _TILE_SIZE * _RADAR_SCALE - _CROP_TOP,
)

_RECTANGLE_COORDS = (2266, 2029, 2341, 2079)
_FLOODFILL_POS = (3839, 2159)
_FLOODFILL_THRESH = 140


def _assemble_tiles(tiles: list[Path], columns: int) -> Image.Image:
    images = [Image.open(t) for t in tiles]
    rows = (len(images) + columns - 1) // columns
    width = columns * _TILE_SIZE
    height = rows * _TILE_SIZE
    canvas = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    for i, img in enumerate(images):
        col = i % columns
        row = i // columns
        canvas.paste(img, (col * _TILE_SIZE, row * _TILE_SIZE))
    return canvas


def composite_radar_image(background: Image.Image, radar_path: Path, opacity: float) -> Image.Image:
    radar = Image.open(radar_path).convert('RGBA')
    radar = radar.resize(_RADAR_SIZE, Image.LANCZOS)
    alpha = radar.split()[3]
    alpha = alpha.point(lambda p: int(p * opacity))
    radar.putalpha(alpha)
    background.paste(radar, _RADAR_PASTE_OFFSET, radar)
    return background.convert('RGB')


def _composite_radar(background_path: Path, radar_path: Path, output_path: Path, opacity: float) -> None:
    background = Image.open(background_path).convert('RGBA')
    composite_radar_image(background, radar_path, opacity).save(output_path)


def _apply_background_overlays(img: Image.Image) -> None:
    draw = ImageDraw.Draw(img)
    draw.rectangle(_RECTANGLE_COORDS, fill='#9c9c9c')


def _make_dark_variant(img: Image.Image) -> Image.Image:
    white = Image.new('RGB', img.size, (255, 255, 255))
    white.paste(img.convert('RGBA'), mask=img.split()[3])
    img_dark = ImageOps.invert(white)
    ImageDraw.floodfill(img_dark, _FLOODFILL_POS, (41, 41, 41), thresh=_FLOODFILL_THRESH)
    return img_dark
