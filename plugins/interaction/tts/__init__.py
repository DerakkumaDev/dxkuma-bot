import os
import re
from pathlib import Path

import aiofiles
from httpx import AsyncClient
from nonebot import on_regex
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    MessageEvent,
    MessageSegment,
)
from xxhash import xxh32_hexdigest

from util.config import config
from util.permission import ADMIN
from util.stars import stars

tts = on_regex(r"^(迪拉熊|dlx)(说：?|say|speak|t[2t][as])", re.I)
tts_dev = on_regex(
    r"^(迪拉熊|dlx)dev(说：?|say|speak|t[2t][as])", re.I, permission=ADMIN
)


@tts.handle()
async def _(event: MessageEvent):
    qq = event.get_user_id()
    msg = event.get_plaintext()
    match = re.fullmatch(
        r"^(?:迪拉熊|dlx)(?:说：?|say|speak|t[2t][as])(.+)", msg, re.I | re.S
    )
    if not match:
        return

    if not (text := match.group(1)):
        return

    balance = await stars.get_balance(qq)
    if balance == "inf":
        pass
    elif balance == 0:
        await tts.finish("你没有★了哦~", at_sender=True)
    elif balance < 0:
        await tts.finish(f"你还欠迪拉熊{-balance}颗★呢（哼）", at_sender=True)

    audio, _, usage_characters = await text_to_speech(text)
    if not await stars.apply_change(qq, -usage_characters, "让迪拉熊说话", event.time):
        raise
    balance = await stars.get_balance(qq)
    if balance == "inf":
        msg = f"迪拉熊吃掉了{usage_characters}颗★mai~你现在还有∞颗★哦~"
    elif balance > 0:
        msg = f"迪拉熊吃掉了{usage_characters}颗★mai~你现在还有{balance}颗★哦~"
    elif balance < 0:
        msg = f"迪拉熊吃掉了{usage_characters}颗★mai~你现在欠迪拉熊{-balance}颗★了mai！"
    else:
        msg = f"迪拉熊吃掉了{usage_characters}颗★mai~你现在没有★了mai~"
    await tts.send(MessageSegment.record(audio))
    await tts.send(msg, at_sender=True)


@tts_dev.handle()
async def _(bot: Bot, event: MessageEvent):
    msg = str(event.get_message())
    if not (
        match := re.fullmatch(
            r"^(?:迪拉熊|dlx)dev(?:说：?|say|speak|t[2t][as])(.+)", msg, re.I | re.S
        )
    ):
        return

    if not (text := match.group(1)):
        return

    audio, subtitle_file, _ = await text_to_speech(text)
    hexhash = xxh32_hexdigest(audio)
    file_name = f"{hexhash}.mp3"
    file_path = Path("./Cache/") / "TTS" / file_name
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
        await tts.send(f"字幕文件下载链接：{subtitle_file}")


async def text_to_speech(text: str) -> tuple[bytes, str, int]:
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
            "latex_read": True,
        },
        "pronunciation_dict": {"tone": ["maimai/(mai1)(mai1)"]},
        "language_boost": "auto",
    }

    async with AsyncClient(http2=True) as session:
        resp = await session.post(
            "https://api.minimaxi.com/v1/t2a_v2", json=payload, headers=headers
        )
        audio_info = resp.json()

    data = audio_info.get("data", dict())
    if not (audio := data.get("audio")):
        raise Exception(audio_info["base_resp"]["status_msg"])

    subtitle_file = data.get("subtitle_file")
    extra_info = audio_info.get("extra_info", dict())
    usage_characters = extra_info.get("usage_characters", 1)
    if usage_characters <= 0:
        usage_characters = 1

    return bytes.fromhex(audio), subtitle_file, usage_characters
