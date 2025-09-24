from httpx import AsyncClient, URL

from util.config import config

base_url = "https://www.diving-fish.com/api/maimaidxprober/"


async def get_player_data(qq: str):
    payload = {"qq": qq, "b50": True}
    async with AsyncClient(http2=True, follow_redirects=True) as session:
        resp = await session.post(URL(f"{base_url}query/player"), json=payload)
        if resp.is_error:
            return None, resp.status_code
        obj = resp.json()
        return obj, resp.status_code


async def get_player_records(qq: str):
    headers = {"Developer-Token": config.df_token}
    payload = {"qq": qq}
    async with AsyncClient(http2=True, follow_redirects=True) as session:
        resp = await session.get(
            URL(f"{base_url}dev/player/records"),
            headers=headers,
            params=payload,
        )
        if resp.is_error:
            return None, resp.status_code
        obj = resp.json()
        return obj, resp.status_code


async def get_player_record(qq: str, music_id: str | int):
    headers = {"Developer-Token": config.df_token}
    payload = {"qq": qq, "music_id": music_id}
    async with AsyncClient(http2=True, follow_redirects=True) as session:
        resp = await session.post(
            URL(f"{base_url}dev/player/record"),
            headers=headers,
            json=payload,
        )
        if resp.is_error:
            return None, resp.status_code
        obj = resp.json()
        return obj, resp.status_code
