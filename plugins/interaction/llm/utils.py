from anyio.to_thread import run_sync
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageEvent,
    MessageSegment,
)
from volcenginesdkarkruntime import Ark

from util.Config import config

client = Ark(api_key=config.ark_api_key)


def escape(message: str) -> str:
    return (
        message.replace('"', "&quot;")
        .replace("'", "&apos;")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .strip()
    )


async def gen_message(
    event: MessageEvent, bot: Bot, group_id: int | None = None
) -> str:
    l = list()
    if event.reply:
        reply_msg = event.reply
        l.append(
            f'<reply sender_id="{reply_msg.sender.user_id}" sender_name="{escape(reply_msg.sender.card or reply_msg.sender.nickname or "")}">{"".join(await gen_message_segment(seg, bot, group_id) for seg in reply_msg.message)}</reply>'
        )
    for seg in event.get_message():
        l.append(await gen_message_segment(seg, bot, group_id))
    return "".join(l)


async def gen_message_segment(
    seg: MessageSegment, bot: Bot, group_id: int | None
) -> str:
    if seg.type == "text":
        return escape(seg.data.get("text", ""))
    elif seg.type == "at":
        user_name = escape(seg.data.get("name", ""))
        if not user_name:
            if group_id:
                user_info = await bot.get_group_member_info(
                    group_id=group_id, user_id=int(seg.data.get("qq", "0"))
                )
                user_name = user_info["card"] or user_info["nickname"]
            else:
                user_info = await bot.get_stranger_info(
                    user_id=int(seg.data.get("qq", "0"))
                )
                user_name = user_info["nickname"]
        return f'<at user_id="{seg.data.get("qq", "")}">{user_name}</at>'
    elif seg.type == "poke":
        return f'<poke user_id="{seg.data.get("id", "")}">{escape(seg.data.get("name", ""))}</poke>'
    elif seg.type == "share":
        return f'<share href="{escape(seg.data.get("url", ""))}">{escape(seg.data.get("title", ""))}</share>'
    elif seg.type == "contact":
        return f'<contact type="{seg.data.get("type", "")}">{seg.data.get("id", "")}</contact>'
    elif seg.type == "location":
        return f"<location>{escape(seg.data.get('title', ''))}</location>"
    elif seg.type == "music":
        return f"<music>{escape(seg.data.get('title', ''))}</music>"
    elif seg.type == "reply":
        reply_msg = await bot.get_msg(message_id=seg.data.get("id", 0))
        return f"<reply>{escape(''.join(segg['data']['text'] for segg in reply_msg['message'] if segg['type'] == 'text'))}</reply>"
    elif seg.type == "forward":
        forward_msg = await bot.get_forward_msg(id=seg.data.get("id", ""))
        return f"<forward>{escape(str(forward_msg))}</forward>"
    elif seg.type == "image":
        url = seg.data.get("url", "")
        if not url:
            return f"<{seg.type}/>"
        return f"<image>{escape(await gen_image_info(url))}</image>"
    else:
        return f"<{seg.type}/>"


async def gen_image_info(url: str) -> str:
    return "\r\n".join(
        choice.message.content
        for choice in (
            await run_sync(
                lambda: client.chat.completions.create(
                    model="doubao-seed-1-6-flash-250715",
                    messages=[
                        {
                            "content": [
                                {
                                    "image_url": {"url": url},
                                    "type": "image_url",
                                },
                                {
                                    "text": "现在你是一名专业的高级数据标记员，请你用干练的语言为LLM尽可能详细的解释这张图片。你的回复中不要包含任何主观内容，只需要描述图片中的内容。",
                                    "type": "text",
                                },
                            ],
                            "role": "user",
                        }
                    ],
                )
            )
        ).choices
    )
