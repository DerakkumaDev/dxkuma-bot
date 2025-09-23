import os
from asyncio import Lock
from datetime import date
from pathlib import Path
from typing import Optional

import aiofiles
import orjson as json
from httpx import AsyncClient, HTTPError

music_data_lock = Lock()
music_data_lxns_lock = Lock()
chart_stats_lock = Lock()
alias_list_lxns_lock = Lock()
alias_list_ycn_lock = Lock()
alias_list_xray_lock = Lock()


CACHE_ROOT_PATH = Path("./Cache") / "Data"


async def _get_data(key: str | Path, url: str, params: Optional[dict] = None):
    cache_dir = CACHE_ROOT_PATH / key
    cache_path = cache_dir / f"{date.today().isoformat()}.json"
    if not os.path.exists(cache_path):
        files = os.listdir(cache_dir)
        async with AsyncClient(http2=True) as session:
            try:
                resp = await session.get(url)
            except HTTPError:
                if files:
                    async with aiofiles.open(cache_dir / files[-1]) as fd:
                        return json.loads(await fd.read())
                return await _get_data(key, url, params)
            if resp.status_code != 200:
                if files:
                    async with aiofiles.open(cache_dir / files[-1]) as fd:
                        return json.loads(await fd.read())
                return await _get_data(key, url, params)
            async with aiofiles.open(cache_path, "wb") as fd:
                await fd.write(await resp.aread())
        if files:
            for file in files:
                os.remove(cache_dir / file)
    async with aiofiles.open(cache_path) as fd:
        try:
            return json.loads(await fd.read())
        except json.JSONDecodeError:
            os.remove(cache_path)
            return await _get_data(key, url, params)


async def get_music_data_df():
    async with music_data_lock:
        return await _get_data(
            "MusicData", "https://www.diving-fish.com/api/maimaidxprober/music_data"
        )


async def get_music_data_lxns():
    async with music_data_lxns_lock:
        return await _get_data(
            "MusicDataLxns",
            "https://maimai.lxns.net/api/v0/maimai/song/list",
            {"notes": "true"},
        )


async def get_chart_stats():
    async with chart_stats_lock:
        return await _get_data(
            "ChartStats", "https://www.diving-fish.com/api/maimaidxprober/chart_stats"
        )


async def get_alias_list_lxns():
    async with alias_list_lxns_lock:
        return await _get_data(
            "Alias/Lxns", "https://maimai.lxns.net/api/v0/maimai/alias/list"
        )


async def get_alias_list_ycn():
    async with alias_list_ycn_lock:
        return await _get_data(
            "Alias/YuzuChaN", "https://www.yuzuchan.moe/api/maimaidx/maimaidxalias"
        )


async def get_alias_list_xray():
    async with alias_list_xray_lock:
        return await _get_data(
            "Alias/Xray", "https://download.xraybot.site/maimai/alias.json"
        )
