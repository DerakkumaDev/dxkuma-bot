from datetime import datetime
from typing import Optional

from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageEvent,
    GroupMessageEvent,
    MessageSegment,
)
from openai import AsyncOpenAI
from xxhash import xxh32_hexdigest

from util.Config import config

client = AsyncOpenAI(base_url=config.llm_base_url, api_key=config.llm_api_key)

with open("prompt/system.md", "r") as f:
    system_prompt = f.read()
with open("prompt/user.md", "r") as f:
    user_prompt = f.read()
prompt_hash = xxh32_hexdigest(system_prompt)


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
    event: MessageEvent,
    bot: Bot,
    is_chat_mode: bool,
    medias: list[dict[str, str | float]],
) -> str:
    group_id = event.group_id if isinstance(event, GroupMessageEvent) else None
    l = list()
    if event.reply:
        reply_msg = event.reply
        l.append(
            f"<reply{
                gen_name_field(
                    'sender',
                    str(reply_msg.sender.user_id),
                    reply_msg.sender.card or reply_msg.sender.nickname or str(),
                )
            }>{
                str().join(
                    [
                        await gen_message_segment(seg, bot, group_id, medias)
                        for seg in reply_msg.message
                    ]
                )
            }</reply>"
        )

    if event.is_tome() and is_chat_mode:
        l.append("<at>迪拉熊</at>")

    for seg in event.get_message():
        l.append(await gen_message_segment(seg, bot, group_id, medias))

    return str().join(l)


async def gen_message_segment(
    seg: MessageSegment | dict[str, dict[str, str]],
    bot: Bot,
    group_id: Optional[int],
    medias: list[dict[str, str | float]],
) -> str:
    if isinstance(seg, dict):
        seg = MessageSegment(seg.get("type", str()), seg.get("data", dict()))

    if seg.type == "text":
        return escape(seg.data.get("text", str()))
    elif seg.type == "at":
        user_id = seg.data.get("qq", "0")
        if user_id == "all":
            return "<at_all/>"

        user_name = escape(seg.data.get("name", str()))
        if not user_name:
            if group_id:
                user_info = await bot.get_group_member_info(
                    group_id=group_id, user_id=int(user_id)
                )
                user_name = escape(
                    user_info.get("card", str()) or user_info.get("nickname", str())
                )
            else:
                user_info = await bot.get_stranger_info(user_id=int(user_id))
                user_name = escape(user_info.get("nickname", str()))

        return f"<at{gen_name_field('user', user_id, user_name, True)}</at>"
    elif seg.type == "poke":
        user_id = seg.data.get("id", "0")
        if group_id:
            user_info = await bot.get_group_member_info(
                group_id=group_id, user_id=int(user_id)
            )
            user_name = escape(
                user_info.get("card", str()) or user_info.get("nickname", str())
            )
        else:
            user_info = await bot.get_stranger_info(user_id=int(user_id))
            user_name = escape(user_info.get("nickname", str()))

        return f'<poke type="{escape(seg.data.get("type", str()))}"{
            gen_name_field("user", user_id, user_name, True)
        }</poke>'
    elif seg.type == "contact":
        contact_type = seg.data.get("type", str())
        contact_id = seg.data.get("id", "0")
        contact_name = str()
        if contact_type == "qq":
            user_info = await bot.get_stranger_info(user_id=int(contact_id))
            contact_name = escape(user_info.get("nickname", str()))
        elif contact_type == "group":
            group_info = await bot.get_group_info(group_id=int(contact_id))
            contact_name = escape(group_info.get("card", str()))
        return f'<contact type="{contact_type}"{gen_name_field("contact", contact_id, contact_name, True)}</contact>'
    elif seg.type == "music":
        return f"<music>{escape(seg.data.get('title', str()))}</music>"
    elif seg.type == "reply":
        try:
            reply_msg = await bot.get_msg(message_id=seg.data.get("id", 0))
        except Exception:
            return "<reply/>"
        sender = reply_msg.get("sender", dict())
        return f"<reply{
            gen_name_field(
                'sender',
                sender.get('user_id', str()),
                sender.get('card', str()) or sender.get('nickname', str()),
            )
        }>{
            str().join(
                [
                    await gen_message_segment(sub_seg, bot, group_id, medias)
                    for sub_seg in reply_msg.get('message', list())
                ]
            )
        }</reply>"
    elif seg.type == "forward":
        forward_messages = seg.data.get("content", list())
        if not forward_messages:
            try:
                forward_msg = await bot.get_forward_msg(id=seg.data.get("id", str()))
            except Exception:
                return "<forward/>"
            forward_messages = forward_msg.get("messages", list())
        messages = list()
        for message in forward_messages:
            now = datetime.fromtimestamp(
                message.get("time", datetime.now().timestamp())
            )
            sender = message.get("sender", dict())
            msg_text = str().join(
                [
                    await gen_message_segment(sub_seg, bot, group_id, medias)
                    for sub_seg in message.get("message", list())
                ]
            )
            if message.get("message_type", "private") != "group":
                messages.append(
                    f'<message time="{now.isoformat()}" sender_id="{
                        sender.get("user_id", str())
                    }" sender_name="{escape(sender.get("nickname", str()))}">\n'
                    f"{msg_text}\n"
                    "</message>"
                )
                continue

            try:
                group_info = await bot.get_group_info(
                    group_id=message.get("group_id", 0)
                )
            except Exception:
                group_info = dict()
            group_name = group_info.get("group_name", str())
            messages.append(
                f'<message time="{now.isoformat()}" chatroom_name="{
                    escape(group_name)
                }" sender_id="{sender.get("user_id", str())}" sender_name="{
                    escape(sender.get("nickname", str()))
                }">\n'
                f"{msg_text}\n"
                "</message>"
            )
        return f"<forward>{str().join(messages)}</forward>"
    elif seg.type == "image":
        url = seg.data.get("url", str())
        if not url:
            return f"<image>{escape(seg.data.get('name', str()))}</image>"

        result = f'<image index="{len(medias)}"/>'
        medias.append({"type": "image", "url": url})
        return result
    elif seg.type == "face":
        return f"<face>{escape(seg.data.get('raw', dict()).get('faceText', str()) or str())}</face>"
    elif seg.type == "video":
        url = seg.data.get("url", str())
        if not url:
            return f"<video>{escape(seg.data.get('name', str()))}</video>"

        result = f'<video index="{len(medias)}"/>'
        medias.append({"type": "video", "url": url})
        return result
    elif seg.type == "record":
        return f"<record>{escape(seg.data.get('name', str()))}</record>"
    elif seg.type == "file":
        return f"<file>{escape(seg.data.get('name', str()))}</file>"
    elif seg.type == "mface":
        return f"<mface>{escape(seg.data.get('summary', str()))}</mface>"
    elif seg.type == "markdown":
        return f"<markdown>{escape(seg.data.get('content', str()))}</markdown>"
    elif seg.type == "dice":
        return f"<dice>{escape(seg.data.get('result', str()))}</dice>"
    elif seg.type == "rps":
        return f"<rps>{escape(seg.data.get('result', str()))}</rps>"
    else:
        return f"<{seg.type}>{seg.data}<{seg.type}/>"


def gen_name_field(key: str, user_id: str, name: str, name_value: bool = False) -> str:
    name = escape(name)
    if name_value:
        if user_id in config.bots:
            return ">迪拉熊"
        else:
            return f' {key}_id="{user_id}">{name}'
    else:
        if user_id in config.bots:
            return f' {key}="迪拉熊"'
        elif not name:
            return f' {key}_id="{user_id}"'
        else:
            return f' {key}_id="{user_id}" {key}_name="{name}"'
