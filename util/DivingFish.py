from aiohttp import ClientSession

import orjson as json
from util.Config import config

base_url = "https://www.diving-fish.com/api/maimaidxprober/"


async def get_player_data(qq: str):
    payload = {"qq": qq, "b50": True}
    async with ClientSession(conn_timeout=3) as session:
        async with session.post(f"{base_url}query/player", json=payload) as resp:
            if resp.status == 200:
                obj = await resp.json(loads=json.loads)
                return obj, 200
            return None, resp.status


async def get_player_records(qq: str):
    headers = {"Developer-Token": config.df_token}
    payload = {"qq": qq}
    async with ClientSession(conn_timeout=3) as session:
        async with session.get(
            f"{base_url}dev/player/records",
            headers=headers,
            params=payload,
        ) as resp:
            if resp.status == 200:
                obj = await resp.json(loads=json.loads)
                return obj, 200
            return None, resp.status


async def get_player_record(qq: str, music_id: str | int):
    headers = {"Developer-Token": config.df_token}
    payload = {"qq": qq, "music_id": music_id}
    async with ClientSession(conn_timeout=3) as session:
        async with session.post(
            f"{base_url}dev/player/record",
            headers=headers,
            json=payload,
        ) as resp:
            if resp.status == 200:
                obj = await resp.json(loads=json.loads)
                return obj, 200
            return None, resp.status
