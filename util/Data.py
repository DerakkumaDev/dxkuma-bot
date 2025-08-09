import os
from asyncio import Lock
from datetime import date

import aiofiles
import orjson as json
from httpx import HTTPError, AsyncClient

music_data_lock = Lock()
chart_stats_lock = Lock()
alias_list_lxns_lock = Lock()
alias_list_ycn_lock = Lock()
alias_list_xray_lock = Lock()


async def get_music_data_df():
    cache_dir = "./Cache/Data/MusicData/"
    cache_path = f"{cache_dir}{date.today().isoformat()}.json"
    async with music_data_lock:
        if not os.path.exists(cache_path):
            files = os.listdir(cache_dir)
            async with AsyncClient(http2=True, timeout=3) as session:
                try:
                    resp = await session.get(
                        "https://www.diving-fish.com/api/maimaidxprober/music_data"
                    )
                    async with aiofiles.open(cache_path, "wb") as fd:
                        await fd.write(await resp.aread())
                except HTTPError:
                    if os.path.exists(cache_path):
                        os.remove(cache_path)
                    if files:
                        async with aiofiles.open(f"{cache_dir}{files[-1]}") as fd:
                            return json.loads(await fd.read())
                    return await get_music_data_df()
            if files:
                for file in files:
                    os.remove(f"{cache_dir}{file}")
        async with aiofiles.open(cache_path) as fd:
            try:
                return json.loads(await fd.read())
            except json.JSONDecodeError:
                os.remove(cache_path)
                return await get_music_data_df()


async def get_music_data_lxns():
    cache_dir = "./Cache/Data/MusicDataLxns/"
    cache_path = f"{cache_dir}{date.today().isoformat()}.json"
    async with music_data_lock:
        if not os.path.exists(cache_path):
            files = os.listdir(cache_dir)
            async with AsyncClient(http2=True, timeout=3) as session:
                try:
                    resp = await session.get(
                        "https://maimai.lxns.net/api/v0/maimai/song/list",
                        params={"notes": "true"},
                    )
                    async with aiofiles.open(cache_path, "wb") as fd:
                        await fd.write(await resp.aread())
                except HTTPError:
                    if os.path.exists(cache_path):
                        os.remove(cache_path)
                    if files:
                        async with aiofiles.open(f"{cache_dir}{files[-1]}") as fd:
                            return json.loads(await fd.read())
                    return await get_music_data_lxns()
            if files:
                for file in files:
                    os.remove(f"{cache_dir}{file}")
        async with aiofiles.open(cache_path) as fd:
            try:
                return json.loads(await fd.read())
            except json.JSONDecodeError:
                os.remove(cache_path)
                return await get_music_data_lxns()


async def get_chart_stats():
    cache_dir = "./Cache/Data/ChartStats/"
    cache_path = f"{cache_dir}{date.today().isoformat()}.json"
    async with chart_stats_lock:
        if not os.path.exists(cache_path):
            files = os.listdir(cache_dir)
            async with AsyncClient(http2=True, timeout=3) as session:
                try:
                    resp = await session.get(
                        "https://www.diving-fish.com/api/maimaidxprober/chart_stats"
                    )
                    async with aiofiles.open(cache_path, "wb") as fd:
                        await fd.write(await resp.aread())
                except HTTPError:
                    if os.path.exists(cache_path):
                        os.remove(cache_path)
                    if files:
                        async with aiofiles.open(f"{cache_dir}{files[-1]}") as fd:
                            return json.loads(await fd.read())
                    return await get_chart_stats()
            if files:
                for file in files:
                    os.remove(f"{cache_dir}{file}")
        async with aiofiles.open(cache_path) as fd:
            try:
                return json.loads(await fd.read())
            except json.JSONDecodeError:
                os.remove(cache_path)
                return await get_chart_stats()


async def get_alias_list_lxns():
    cache_dir = "./Cache/Data/Alias/Lxns/"
    cache_path = f"{cache_dir}{date.today().isoformat()}.json"
    async with alias_list_lxns_lock:
        if not os.path.exists(cache_path):
            files = os.listdir(cache_dir)
            async with AsyncClient(http2=True, timeout=3) as session:
                try:
                    resp = await session.get(
                        "https://maimai.lxns.net/api/v0/maimai/alias/list"
                    )
                    async with aiofiles.open(cache_path, "wb") as fd:
                        await fd.write(await resp.aread())
                except HTTPError:
                    if os.path.exists(cache_path):
                        os.remove(cache_path)
                    if files:
                        async with aiofiles.open(f"{cache_dir}{files[-1]}") as fd:
                            return json.loads(await fd.read())
                    return await get_alias_list_lxns()
            if files:
                for file in files:
                    os.remove(f"{cache_dir}{file}")
        async with aiofiles.open(cache_path) as fd:
            try:
                return json.loads(await fd.read())
            except json.JSONDecodeError:
                os.remove(cache_path)
                return await get_alias_list_lxns()


async def get_alias_list_ycn():
    cache_dir = "./Cache/Data/Alias/YuzuChaN/"
    cache_path = f"{cache_dir}{date.today().isoformat()}.json"
    async with alias_list_ycn_lock:
        if not os.path.exists(cache_path):
            files = os.listdir(cache_dir)
            async with AsyncClient(http2=True, timeout=3) as session:
                try:
                    resp = await session.get(
                        "https://www.yuzuchan.moe/api/maimaidx/maimaidxalias"
                    )
                    async with aiofiles.open(cache_path, "wb") as fd:
                        await fd.write(await resp.aread())
                except HTTPError:
                    if os.path.exists(cache_path):
                        os.remove(cache_path)
                    if files:
                        async with aiofiles.open(f"{cache_dir}{files[-1]}") as fd:
                            return json.loads(await fd.read())
                    return await get_alias_list_ycn()
            if files:
                for file in files:
                    os.remove(f"{cache_dir}{file}")
        async with aiofiles.open(cache_path) as fd:
            try:
                return json.loads(await fd.read())
            except json.JSONDecodeError:
                os.remove(cache_path)
                return await get_alias_list_ycn()


async def get_alias_list_xray():
    cache_dir = "./Cache/Data/Alias/Xray/"
    cache_path = f"{cache_dir}{date.today().isoformat()}.json"
    async with alias_list_xray_lock:
        if not os.path.exists(cache_path):
            files = os.listdir(cache_dir)
            async with AsyncClient(http2=True, timeout=3) as session:
                try:
                    resp = await session.get(
                        "https://download.xraybot.site/maimai/alias.json"
                    )
                    async with aiofiles.open(cache_path, "wb") as fd:
                        await fd.write(await resp.aread())
                except HTTPError:
                    if os.path.exists(cache_path):
                        os.remove(cache_path)
                    if files:
                        async with aiofiles.open(f"{cache_dir}{files[-1]}") as fd:
                            return json.loads(await fd.read())
                    return await get_alias_list_xray()
            if files:
                for file in files:
                    os.remove(f"{cache_dir}{file}")
        async with aiofiles.open(cache_path) as fd:
            try:
                return json.loads(await fd.read())
            except json.JSONDecodeError:
                os.remove(cache_path)
                return await get_alias_list_xray()
