import base64
from datetime import datetime, timedelta, timezone
from typing import Optional

from httpx import AsyncClient, HTTPError
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    MessageEvent,
    MessageSegment,
)
from volcenginesdkarkruntime import AsyncArk
from xxhash import xxh32_hexdigest

from util.config import config

client = AsyncArk(api_key=config.llm_api_key)

with open("prompt/system.md", "r") as f:
    system_prompt = f.read()
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


async def gen_message(event: MessageEvent, bot: Bot) -> str:
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
                        await gen_message_segment(seg, bot, group_id)
                        for seg in reply_msg.message
                    ]
                )
            }</reply>"
        )

    for seg in event.get_message():
        l.append(await gen_message_segment(seg, bot, group_id))

    return str().join(l)


async def gen_message_segment(
    seg: MessageSegment | dict[str, dict[str, str]], bot: Bot, group_id: Optional[int]
) -> str:
    if isinstance(seg, dict):
        seg = MessageSegment(seg.get("type", str()), seg.get("data", dict()))

    if seg.type == "text":
        return escape(seg.data.get("text", str()))
    elif seg.type == "at":
        user_id = seg.data.get("qq", "0")
        if user_id == "all":
            return "<at_all />"

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
        return gen_seg("music", escape(seg.data.get("title", str())))
    elif seg.type == "reply":
        try:
            reply_msg = await bot.get_msg(message_id=seg.data.get("id", 0))
        except Exception:
            return "<quote />"
        sender = reply_msg.get("sender", dict())
        return f"<quote{
            gen_name_field(
                'sender',
                sender.get('user_id', str()),
                sender.get('card', str()) or sender.get('nickname', str()),
            )
        }>{
            str().join(
                [
                    await gen_message_segment(sub_seg, bot, group_id)
                    for sub_seg in reply_msg.get('message', list())
                ]
            )
        }</quote>"
    elif seg.type == "forward":
        forward_messages = seg.data.get("content", list())
        if not forward_messages:
            try:
                forward_msg = await bot.get_forward_msg(id=seg.data.get("id", str()))
            except Exception:
                return "<forward />"
            forward_messages = forward_msg.get("messages", list())
        messages = list()
        for message in forward_messages:
            now = datetime.fromtimestamp(
                message.get(
                    "time", datetime.now(timezone(timedelta(hours=8))).timestamp()
                )
            )
            sender = message.get("sender", dict())
            msg_text = str().join(
                [
                    await gen_message_segment(sub_seg, bot, group_id)
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
        return gen_seg("forward", str().join(messages))
    elif seg.type == "image":
        if url := seg.data.get("url"):
            file = seg.data.get("file", str())
            info = await gen_image_info(url, file)
        else:
            info = seg.data.get("name", str())
        return gen_seg("image", escape(info))
    elif seg.type == "face":
        return gen_seg(
            "emoji", escape(seg.data.get("raw", dict()).get("faceText", str()) or str())
        )
    elif seg.type == "video":
        if url := seg.data.get("url"):
            file = seg.data.get("file", str())
            info = await gen_vedio_info(url, file)
        else:
            info = seg.data.get("name", str())
        return gen_seg("video", escape(info))
    elif seg.type == "record":
        return gen_seg("record", escape(seg.data.get("name", str())))
    elif seg.type == "file":
        return gen_seg("file", escape(seg.data.get("name", str())))
    elif seg.type == "mface":
        return gen_seg("emoticon", escape(seg.data.get("summary", str())))
    elif seg.type == "markdown":
        return gen_seg("markdown", escape(seg.data.get("content", str())))
    elif seg.type == "dice":
        return gen_seg("dice", escape(seg.data.get("result", str())))
    elif seg.type == "rps":
        return gen_seg("rps", escape(seg.data.get("result", str())))
    else:
        return gen_seg(seg.type, escape(str(seg.data)))


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


def gen_seg(key: str, value: str) -> str:
    if not value:
        return f"<{key} />"
    return f"<{key}>{value}<{key}/>"


async def gen_image_info(url: str, file: str) -> str:
    url_or_base = await _get_media_url("image", url, file.split(".")[-1])
    content = {"url": url_or_base, "detail": "low"}
    try:
        return await _gen_media_info("image_url", content)
    except Exception:
        return str()


async def gen_vedio_info(url: str, file: str) -> str:
    url_or_base = await _get_media_url("video", url, file.split(".")[-1])
    content = {"url": url_or_base, "fps": 0.2}
    try:
        return await _gen_media_info("video_url", content, True)
    except Exception:
        return str()


async def _get_media_url(content_type: str, url: str, format: str) -> str:
    async with AsyncClient(http2=True, follow_redirects=True) as session:
        try:
            resp = await session.get(url)
        except HTTPError:
            return url

        if resp.is_error:
            return url

        encoded_data = base64.b64encode(resp.content).decode()
        return f"data:{content_type}/{format};base64,{encoded_data}"


async def _gen_media_info(
    content_type: str, content: dict, disable_encrypted: bool = False
) -> str:
    response = await client.chat.completions.create(
        model=config.vision_llm_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": content_type, content_type: content},
                    {"type": "text", "text": config.vision_llm_prompt},
                ],
            }
        ],
        extra_headers=None if disable_encrypted else {"x-is-encrypted": "true"},
    )
    return str().join(
        choice.message.content
        for choice in response.choices
        if choice.message.content is not None
    )
