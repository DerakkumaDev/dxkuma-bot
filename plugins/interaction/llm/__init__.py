from datetime import datetime

from anyio import Lock
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

locks: dict[str, Lock] = dict()

handler = on_message(priority=10000, block=False)


@handler.handle()
async def _(bot: Bot, event: MessageEvent):
    now = datetime.now()
    if isinstance(event, GroupMessageEvent):
        user_name = event.sender.card or event.sender.nickname or str()
        msg_text = await gen_message(event, bot)
        chat_id = f"{event.group_id}.g"
        group_name = (await bot.get_group_info(group_id=event.group_id))["group_name"]
        message = str.format(
            config.llm_user_prompt,
            f'<message time="{now.isoformat()}" chatroom_name="{escape(group_name)}" sender_id="{event.get_user_id()}" sender_name="{escape(user_name)}">\n{msg_text}\n</message>',
        )
    else:
        user_name = event.sender.nickname
        msg_text = await gen_message(event, bot)
        chat_id = f"{event.get_user_id()}.p"
        message = str.format(
            config.llm_user_prompt,
            f'<message time="{now.isoformat()}" sender_id="{event.get_user_id()}" sender_name="{escape(user_name)}">\n{msg_text}\n</message>',
        )

    if not msg_text:
        return

    if chat_id not in locks:
        locks[chat_id] = Lock()

    async with locks[chat_id]:
        context_id = contextIdList.get(chat_id)
        if context_id is None:
            response = await run_sync(
                lambda: client.context.create(
                    model="ep-20250724172944-7s56v",
                    messages=[{"role": "system", "content": config.llm_system_prompt}],
                    mode="session",
                    truncation_strategy={
                        "type": "rolling_tokens",
                        "rolling_tokens": True,
                    },
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
    if reply == "<ignored/>":
        return

    await handler.send(reply)
