import os
from asyncio import Lock
from pathlib import Path

import aiofiles
from PIL import Image, UnidentifiedImageError
from PIL.ImageFile import ImageFile
from httpx import AsyncClient
from soundfile import LibsndfileError, SoundFile

res_lock: dict[str, Lock] = dict()

CACHE_ROOT = Path("Cache")


async def _check_res(path: str | os.PathLike[str] | Path, url: str):
    if os.path.exists(path):
        return

    async with AsyncClient(http2=True) as session:
        resp = await session.get(url)
        if resp.is_error:
            resp.raise_for_status()

        async with aiofiles.open(path, "wb") as fd:
            async for chunk in resp.aiter_bytes():
                await fd.write(chunk)


async def _get_image(key: str, value: str | int, url: str) -> ImageFile:
    path = CACHE_ROOT / key / f"{value}.png"
    async with res_lock.setdefault(f"{key}_{value}", Lock()):
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

    return Image.open(path)


async def _get_audio(key: str, value: str | int, url: str) -> SoundFile:
    path = CACHE_ROOT / key / f"{value}.mp3"
    async with res_lock.setdefault(f"{key}_{value}", Lock()):
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
