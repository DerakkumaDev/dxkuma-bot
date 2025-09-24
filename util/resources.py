import os
from pathlib import Path

import aiofiles
from PIL import Image, UnidentifiedImageError
from PIL.ImageFile import ImageFile
from cloudscraper import CloudScraper
from soundfile import LibsndfileError, SoundFile

CACHE_ROOT = Path("Cache")


async def _check_res(path: str | os.PathLike[str] | Path, url: str):
    if os.path.exists(path):
        return

    with CloudScraper() as scraper:
        resp = scraper.get(url)
        async with aiofiles.open(path, "wb") as fd:
            await fd.write(resp.content)


async def _get_image(key: str, value: str | int, url: str) -> ImageFile:
    path = CACHE_ROOT / key / f"{value}.png"
    await _check_res(path, url)
    try:
        image = Image.open(path)
    except UnidentifiedImageError:
        os.remove(path)
        return await _get_image(key, value, url)

    try:
        image.verify()
    except OSError:
        os.remove(path)
        return await _get_image(key, value, url)

    image.close()
    return Image.open(path)


async def _get_audio(key: str, value: str | int, url: str) -> SoundFile:
    path = CACHE_ROOT / key / f"{value}.mp3"
    await _check_res(path, url)
    try:
        audio = SoundFile(path)
    except LibsndfileError:
        os.remove(path)
        return await _get_audio(key, value, url)

    return audio


async def get_icon(res_id: str | int) -> ImageFile:
    url = f"https://assets2.lxns.net/maimai/icon/{res_id}.png"
    return await _get_image("Icon", res_id, url)


async def get_plate(res_id: str | int) -> ImageFile:
    url = f"https://assets2.lxns.net/maimai/plate/{res_id}.png"
    return await _get_image("Plate", res_id, url)


async def get_frame(res_id: str | int) -> ImageFile:
    url = f"https://assets2.lxns.net/maimai/frame/{res_id}.png"
    return await _get_image("Frame", res_id, url)


async def get_jacket(song_id: str | int) -> ImageFile:
    url = f"https://assets2.lxns.net/maimai/jacket/{song_id}.png"
    return await _get_image("Jacket", song_id, url)


async def get_music(song_id: str | int) -> SoundFile:
    url = f"https://assets2.lxns.net/maimai/music/{song_id}.mp3"
    return await _get_audio("Music", song_id, url)
