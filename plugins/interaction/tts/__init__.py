import re

from httpx import AsyncClient, URL
from nonebot import on_regex
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment

from util.config import config
from util.stars import stars

tts = on_regex(r"^(迪拉熊|dlx)(说：?|say|speak|t[2t][as])\s*.", re.I)


@tts.handle()
async def _(event: MessageEvent):
    qq = event.get_user_id()
    msg = event.get_plaintext()
    match = re.fullmatch(
        r"^(?:迪拉熊|dlx)(?:说：?|say|speak|t[2t][as])\s*(.+?)\s*", msg, re.I | re.S
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

    audio, usage_characters = await text_to_speech(text)
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


async def text_to_speech(text: str) -> tuple[bytes, int]:
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

    async with AsyncClient(http2=True, follow_redirects=True) as session:
        resp = await session.post(
            URL("https://api.minimaxi.com/v1/t2a_v2"), json=payload, headers=headers
        )
        if resp.is_error:
            resp.raise_for_status()
        audio_info = resp.json()

    data = audio_info.get("data", dict())
    if not (audio := data.get("audio")):
        raise Exception(audio_info["base_resp"]["status_msg"])

    extra_info = audio_info.get("extra_info", dict())
    usage_characters = extra_info.get("usage_characters", 1)
    if usage_characters <= 0:
        usage_characters = 1

    return bytes.fromhex(audio), usage_characters
