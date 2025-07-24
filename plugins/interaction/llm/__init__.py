from datetime import datetime

from anyio.to_thread import run_sync
from nonebot import on_message
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageEvent,
    GroupMessageEvent,
    MessageSegment,
)

from .database import contextIdList
from .utils import client, escape, gen_message
from util.Config import config


handler = on_message(priority=10000, block=False)


@handler.handle()
async def _(bot: Bot, event: MessageEvent):
    now = datetime.now()
    if isinstance(event, GroupMessageEvent):
        user_name = event.sender.card or event.sender.nickname or ""
        msg_text = await gen_message(event, bot, event.group_id)
        chat_id = f"{event.group_id}.g"
        group_name = (await bot.get_group_info(group_id=event.group_id))["group_name"]
        message = f'<system>{config.user_prefix}</system><request time="{now.isoformat()}" chatroom_name="{(group_name)}" sender_id="{event.get_user_id()}" sender_name="{escape(user_name)}">{msg_text}</request>'
    else:
        user_name = event.sender.nickname
        msg_text = await gen_message(event, bot)
        chat_id = f"{event.get_user_id()}.p"
        message = f'<system>{config.user_prefix}</system><request time="{now.isoformat()}" sender_id="{event.get_user_id()}" sender_name="{escape(user_name)}">{msg_text}</request>'

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
