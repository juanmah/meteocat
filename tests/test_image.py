from pathlib import Path

from PIL import Image

from meteocat.image import (
    _RADAR_PASTE_OFFSET,
    _RADAR_SIZE,
    _RECTANGLE_COORDS,
    _TILE_SIZE,
    _apply_background_overlays,
    _assemble_tiles,
    _composite_radar,
    _make_dark_variant,
    composite_radar_image,
)


def test_constants() -> None:
    assert _TILE_SIZE == 256
    assert _RADAR_SIZE == (3 * 256 * 8, 2 * 256 * 8)
    assert _RADAR_PASTE_OFFSET == (
        63 * 256 * 8 - 510 * 256 - 300,
        648 * 256 - 81 * 256 * 8 - 300,
    )
    assert _RECTANGLE_COORDS == (2266, 2029, 2341, 2079)


def test_assemble_tiles(tmp_path: Path) -> None:
    tiles: list[Path] = []
    for i in range(7):
        p = tmp_path / f'tile-{i}.png'
        Image.new('RGBA', (256, 256), (i, i, i, 255)).save(p)
        tiles.append(p)
    canvas = _assemble_tiles(sorted(tiles), columns=3)
    assert canvas.size == (768, 768)
    assert canvas.mode == 'RGBA'


def test_composite_radar_image(tmp_path: Path) -> None:
    background = Image.new('RGBA', (1000, 1000), (10, 10, 10, 255))
    radar_path = tmp_path / 'radar.png'
    Image.new('RGBA', (100, 100), (200, 200, 200, 128)).save(radar_path)
    result = composite_radar_image(background, radar_path, opacity=0.5)
    assert result.mode == 'RGB'


def test_composite_radar_saves_output(tmp_path: Path) -> None:
    background_path = tmp_path / 'background.png'
    radar_path = tmp_path / 'radar.png'
    output_path = tmp_path / 'output.png'
    Image.new('RGBA', (512, 512), (10, 10, 10, 255)).save(background_path)
    Image.new('RGBA', (64, 64), (200, 200, 200, 255)).save(radar_path)
    _composite_radar(background_path, radar_path, output_path, opacity=0.8)
    assert output_path.is_file()


def test_apply_background_overlays() -> None:
    img = Image.new('RGB', (4000, 3000), (0, 0, 0))
    _apply_background_overlays(img)
    x1, y1, _x2, _y2 = _RECTANGLE_COORDS
    assert img.getpixel((x1, y1)) == (0x9C, 0x9C, 0x9C)


def test_make_dark_variant() -> None:
    img = Image.new('RGBA', (100, 100), (255, 255, 255, 255))
    dark = _make_dark_variant(img)
    assert dark.mode == 'RGB'
    assert dark.size == (100, 100)
