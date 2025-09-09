from httpx import AsyncClient
from nonebot import on_startswith
from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageSegment

from util.config import config

speak = on_startswith("迪拉熊说：")


@speak.handle()
async def _(event: GroupMessageEvent):
    headers = {
        "Authorization": f"Bearer {config.tts_api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": config.tts_model,
        "text": event.get_plaintext()[5:],
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

    if (data := audio_info.get("data")) and (audio := data.get("audio")):
        await speak.finish(MessageSegment.record(bytes.fromhex(audio)))

    raise Exception(audio_info["base_resp"]["status_msg"])
