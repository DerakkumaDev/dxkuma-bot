from datetime import datetime

from anyio.to_thread import run_sync
from nonebot import on_message
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    MessageSegment,
)
from volcenginesdkarkruntime import Ark

from .database import contextIdList
from util.Config import config

client = Ark(api_key=config.ark_api_key)

handler = on_message(priority=10000, block=False)


@handler.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    now = datetime.now()
    if event.group_id not in config.llm_enabled_groups:
        return

    user_name = event.sender.card or event.sender.nickname or ""
    msg_text = await m(event, bot, event.group_id)
    chat_id = f"{event.group_id}.g"
    group_name = (await bot.get_group_info(group_id=event.group_id))["group_name"]
    message = f'<system>{config.user_prefix}</system><request time="{now.isoformat()}" chatroom_name="{(group_name)}" sender_id="{event.get_user_id()}" sender_name="{p(user_name)}">{msg_text}</request>'

    if not msg_text:
        return

    context_id = contextIdList.get(chat_id)
    if context_id is None:
        response = await run_sync(
            lambda: client.context.create(
                model="ep-20250724172944-7s56v",
                messages=[{"role": "system", "content": config.llm_prompt}],
                mode="session",
                truncation_strategy={"type": "rolling_tokens", "rolling_tokens": True},
            )
        )
        contextIdList.set(chat_id, context_id := response.id)

    completion = await run_sync(
        lambda: client.context.completions.create(
            model="ep-20250724172944-7s56v",
            context_id=context_id,
            messages=[{"role": "user", "content": message}],
        )
    )
    reply = "\r\n".join(choice.message.content for choice in completion.choices)
    if reply == "<ignored/>" or reply == "&lt;ignored/&gt;":
        return

    await handler.send(MessageSegment.text(reply))


def p(message: str) -> str:
    return (
        message.replace('"', "&quot;")
        .replace("'", "&apos;")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .strip()
    )


async def m(event: GroupMessageEvent, bot: Bot, group_id: int) -> str:
    l = list()
    for seg in event.get_message():
        if isinstance(seg, MessageSegment):
            if seg.type == "text":
                l.append(p(seg.data.get("text", "")))
            elif seg.type == "at":
                user_name = p(seg.data.get("name", ""))
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
                l.append(f'<at user_id="{seg.data.get("qq", "")}">{user_name}</at>')
            elif seg.type == "poke":
                l.append(
                    f'<poke user_id="{seg.data.get("id", "")}">{p(seg.data.get("name", ""))}</poke>'
                )
            elif seg.type == "share":
                l.append(
                    f'<share href="{p(seg.data.get("url", ""))}">{p(seg.data.get("title", ""))}</share>'
                )
            elif seg.type == "contact":
                l.append(
                    f'<contact type="{seg.data.get("type", "")}">{seg.data.get("id", "")}</contact>'
                )
            elif seg.type == "location":
                l.append(f"<location>{p(seg.data.get('title', ''))}</location>")
            elif seg.type == "music":
                l.append(f"<music>{p(seg.data.get('title', ''))}</music>")
            elif seg.type == "reply":
                reply_msg = event.reply
                l.append(
                    f'<reply sender_id="{reply_msg.sender.user_id}" sender_name="{p(reply_msg.sender.card or reply_msg.sender.nickname)}">{p(reply_msg.message.extract_plain_text())}</reply>'
                )
            elif seg.type == "forward":
                forward_msg = await bot.get_forward_msg(id=seg.data.get("id", ""))
                l.append(f"<forward>{p(str(forward_msg))}</forward>")
            elif seg.type == "image":
                url = seg.data.get("url", "")
                if not url:
                    l.append(f"<{seg.type}/>")
                    continue
                l.append(f"<image>{p(await i(url))}</image>")
            else:
                l.append(f"<{seg.type}/>")
    return "".join(l)


async def i(url: str) -> str:
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
                                    "text": "现在你是一名专业的高级数据标记员，请你用干练的语言为LLM尽可能详细的解释这张图片。",
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
