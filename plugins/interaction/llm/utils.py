from anyio.to_thread import run_sync
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageEvent,
    GroupMessageEvent,
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


async def gen_message(event: MessageEvent, bot: Bot) -> str:
    group_id = event.group_id if isinstance(event, GroupMessageEvent) else None
    l = list()
    if event.reply:
        reply_msg = event.reply
        l.append(
            f"<reply{gen_name_field('sender', str(reply_msg.sender.user_id), reply_msg.sender.card or reply_msg.sender.nickname or str())}>{str().join([await gen_message_segment(seg, bot, group_id) for seg in reply_msg.message])}</reply>"
        )
    if event.is_tome():
        l.append("<at>迪拉熊</at>")
    for seg in event.get_message():
        l.append(await gen_message_segment(seg, bot, group_id))
    return str().join(l)


async def gen_message_segment(
    seg: MessageSegment | dict[str, dict[str, str]], bot: Bot, group_id: int | None
) -> str:
    if isinstance(seg, dict):
        seg = MessageSegment(seg.get("type", str()), seg.get("data", dict()))

    if seg.type == "text":
        return escape(seg.data.get("text", str()))
    elif seg.type == "at":
        user_name = escape(seg.data.get("name", str()))
        if not user_name:
            if group_id:
                user_info = await bot.get_group_member_info(
                    group_id=group_id, user_id=int(seg.data.get("qq", "0"))
                )
                user_name = escape(
                    user_info.get("card", str()) or user_info.get("nickname", str())
                )
            else:
                user_info = await bot.get_stranger_info(
                    user_id=int(seg.data.get("qq", "0"))
                )
                user_name = escape(user_info.get("nickname", str()))

        return f"<at{gen_name_field('user', seg.data.get('qq', str()), user_name, True)}</at>"
    elif seg.type == "poke":
        return f"<poke{gen_name_field('user', seg.data.get('id', str()), escape(seg.data.get('name', str())), True)}</poke>"
    elif seg.type == "share":
        return f'<share href="{escape(seg.data.get("url", str()))}">{escape(seg.data.get("title", str()))}</share>'
    elif seg.type == "contact":
        return f'<contact type="{seg.data.get("type", str())}">{seg.data.get("id", str())}</contact>'
    elif seg.type == "location":
        return f"<location>{escape(seg.data.get('title', str()))}</location>"
    elif seg.type == "music":
        return f"<music>{escape(seg.data.get('title', str()))}</music>"
    elif seg.type == "reply":
        try:
            reply_msg = await bot.get_msg(message_id=seg.data.get("id", 0))
        except:
            return "<reply/>"
        sender = reply_msg.get("sender", dict())
        return f"<reply{gen_name_field('sender', sender.get('user_id', str()), sender.get('card', str()) or sender.get('nickname', str()))}>{str().join([await gen_message_segment(sub_seg, bot, group_id) for sub_seg in reply_msg.get('message', list())])}</reply>"
    elif seg.type == "forward":
        try:
            forward_msg = await bot.get_forward_msg(id=seg.data.get("id", str()))
        except:
            return "<forward/>"
        return f"<forward>{escape(str(forward_msg))}</forward>"
    elif seg.type == "image":
        url = seg.data.get("url", str())
        if not url:
            return f"<{seg.type}/>"
        return f"<image>{escape(await gen_image_info(url))}</image>"
    elif seg.type == "face":
        return (
            f"<face>{escape(seg.data.get('raw', dict()).get('faceText', str()))}</face>"
        )
    else:
        return f"<{seg.type}/>"


def gen_name_field(key: str, user_id: str, name: str, name_value: bool = False):
    if name_value:
        if user_id in config.bots:
            return ">迪拉熊"
        else:
            return f' {key}_id="{user_id}">{escape(name)}'
    else:
        if user_id in config.bots:
            return f' {key}="迪拉熊"'
        else:
            return f' {key}_id="{user_id}" {key}_name="{escape(name)}"'


async def gen_image_info(url: str) -> str:
    return "\r\n".join(
        choice.message.content
        for choice in (
            await run_sync(
                lambda: client.chat.completions.create(
                    model="ep-m-20250725142002-m664c",
                    messages=[
                        {
                            "content": [
                                {
                                    "image_url": {"detail": "high", "url": url},
                                    "type": "image_url",
                                },
                                {
                                    "text": "你将作为专业高级数据标记员，用干练语言为大语言模型详细解释一张图片。请仅描述图片内容，不包含任何主观内容。",
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
