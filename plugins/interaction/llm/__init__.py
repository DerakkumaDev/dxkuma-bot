import asyncio
from datetime import datetime

from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageEvent
from nonebot.rule import to_me

from .tasks import on_done, outtime_check, request_queues, times
from .utils import escape, gen_message

handler = on_message(to_me(), priority=1000)


@handler.handle()
async def _(bot: Bot, event: MessageEvent):
    now = datetime.fromtimestamp(event.time)
    if isinstance(event, GroupMessageEvent):
        qqid = event.group_id
        chat_type = "group"
        msg_text = await gen_message(event, bot)
        group_info = await bot.get_group_info(group_id=event.group_id)
        message = (
            f'<message time="{now.isoformat()}" chatroom_name="{
                escape(group_info.get("group_name", str()))
            }" sender_id="{event.user_id}" sender_name="{
                escape(event.sender.card or event.sender.nickname or str())
            }">\n'
            f"{msg_text}\n"
            "</message>"
        )
    else:
        qqid = event.user_id
        chat_type = "private"
        msg_text = await gen_message(event, bot)
        if msg_text.startswith("[自动回复]"):
            return

        message = (
            f'<message time="{now.isoformat()}" sender_id="{qqid}" sender_name="{
                escape(event.sender.nickname)
            }">\n'
            f"{msg_text}\n"
            "</message>"
        )

    if not msg_text:
        return

    chat_id = f"{qqid}.{chat_type[0]}"
    messages = request_queues.setdefault(chat_id, list())
    messages.append(message)
    times[chat_id] = event.time
    task = asyncio.create_task(outtime_check(bot, chat_type, qqid))
    task.add_done_callback(on_done)
