import os
import re
from pathlib import Path

import aiofiles
from httpx import AsyncClient
from nonebot import on_regex
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageEvent
from xxhash import xxh32_hexdigest

from util.config import config
from util.permission import ADMIN

tts_dev = on_regex(
    r"^(迪拉熊|dlx)dev(说：?|say|speak|t[2t][as])\s*.", re.I, permission=ADMIN
)


@tts_dev.handle()
async def _(bot: Bot, event: MessageEvent):
    msg = str(event.get_message())
    if not (
        match := re.fullmatch(
            r"^(?:迪拉熊|dlx)dev(?:说：?|say|speak|t[2t][as])\s*(.+?)\s*",
            msg,
            re.I | re.S,
        )
    ):
        return

    if not (text := match.group(1)):
        return

    audio, subtitle_file = await text_to_speech(text)
    hexhash = xxh32_hexdigest(text)
    file_name = f"{hexhash}.mp3"
    file_path = (Path("Cache") / "TTS" / file_name).resolve()
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(audio)

    if isinstance(event, GroupMessageEvent):
        await bot.call_api(
            "upload_group_file",
            group_id=event.group_id,
            file=file_path.absolute().as_posix(),
            name=file_name,
        )
    else:
        await bot.call_api(
            "upload_private_file",
            user_id=event.user_id,
            file=file_path.absolute().as_posix(),
            name=file_name,
        )

    os.remove(file_path)

    if subtitle_file:
        await tts_dev.send(f"字幕文件下载链接：{subtitle_file}")


async def text_to_speech(text: str) -> tuple[bytes, str]:
    headers = {
        "Authorization": f"Bearer {config.tts_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.tts_model,
        "text": text,
        "voice_setting": {
            "voice_id": config.tts_voice_id,
            "english_normalization": True,
        },
        "pronunciation_dict": {"tone": ["mai/(mai1)"]},
        "language_boost": "auto",
    }

    async with AsyncClient(http2=True) as session:
        resp = await session.post(
            "https://api.minimaxi.com/v1/t2a_v2", json=payload, headers=headers
        )
        resp.raise_for_status()
        audio_info = resp.json()

    data = audio_info.get("data", dict())
    if not (audio := data.get("audio")):
        raise Exception(audio_info["base_resp"]["status_msg"])

    subtitle_file = data.get("subtitle_file")

    return bytes.fromhex(audio), subtitle_file
