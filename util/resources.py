import os
from asyncio import Lock
from pathlib import Path

import aiofiles
import soundfile
from PIL import Image, UnidentifiedImageError
from PIL.ImageFile import ImageFile
from httpx import AsyncClient, HTTPError
from numpy import ndarray

icon_lock: dict[str, Lock] = dict()
plate_lock: dict[str, Lock] = dict()
frame_lock: dict[str, Lock] = dict()
jacket_lock: dict[str, Lock] = dict()
music_lock: dict[str, Lock] = dict()

CACHE_ROOT = Path("Cache")


async def _check_res(path: str | os.PathLike[str] | Path, url: str):
    if os.path.exists(path):
        return

    async with AsyncClient(http2=True) as session:
        try:
            resp = await session.get(url)
        except HTTPError:
            return await _check_res(path, url)

        if resp.is_error:
            resp.raise_for_status()

        async with aiofiles.open(path, "wb") as fd:
            async for chunk in resp.aiter_bytes():
                await fd.write(chunk)


async def _get_image(key: str, value: str, url: str) -> ImageFile:
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

    return Image.open(path)


async def _get_audio(key: str, value: str, url: str) -> tuple[ndarray, int]:
    path = CACHE_ROOT / key / f"{value}.mp3"
    await _check_res(path, url)
    try:
        audio = soundfile.read(path)
    except soundfile.LibsndfileError:
        os.remove(path)
        return await _get_audio(key, value, url)

    return audio


async def get_icon(res_id: str | int) -> ImageFile:
    res_id = str(res_id)
    url = f"https://assets2.lxns.net/maimai/icon/{res_id}.png"
    async with icon_lock.setdefault(res_id, Lock()):
        return await _get_image("Icon", res_id, url)


async def get_plate(res_id: str | int) -> ImageFile:
    res_id = str(res_id)
    url = f"https://assets2.lxns.net/maimai/plate/{res_id}.png"
    async with plate_lock.setdefault(res_id, Lock()):
        return await _get_image("Plate", res_id, url)


async def get_frame(res_id: str | int) -> ImageFile:
    res_id = str(res_id)
    url = f"https://assets2.lxns.net/maimai/frame/{res_id}.png"
    async with frame_lock.setdefault(res_id, Lock()):
        return await _get_image("Frame", res_id, url)


async def get_jacket(song_id: str | int) -> ImageFile:
    song_id = str(song_id)
    url = f"https://assets2.lxns.net/maimai/jacket/{song_id}.png"
    async with jacket_lock.setdefault(song_id, Lock()):
        return await _get_image("Jacket", song_id, url)


async def get_music(song_id: str | int) -> tuple[ndarray, int]:
    song_id = str(song_id)
    url = f"https://assets2.lxns.net/maimai/music/{song_id}.mp3"
    async with music_lock.setdefault(song_id, Lock()):
        return await _get_audio("Music", song_id, url)
