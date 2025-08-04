import asyncio
from datetime import datetime

from nonebot import on_message, on_regex
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, GroupMessageEvent

from .database import contextManager
from .tasks import times, request_queues, outtime_check
from .utils import escape, gen_message

handler = on_message(priority=10000, block=False)

chat_mode_on = on_regex(
    r"^((开启|开始|启用|启动|打开|切换)主动(模式)?|(关闭|禁用|结束)被动(模式)?|(迪拉熊|dlx)说话?)$"
)
chat_mode_off = on_regex(
    r"^((关闭|禁用|结束)主动(模式)?|(开启|开始|启用|启动|打开|切换)被动(模式)?|(迪拉熊|dlx)闭嘴?)$"
)


@handler.handle()
async def _(bot: Bot, event: MessageEvent):
    now = datetime.fromtimestamp(event.time)
    if isinstance(event, GroupMessageEvent):
        qqid = event.group_id
        chat_type = "group"
        chat_id = f"{qqid}.{chat_type[0]}"
        chat_mode = await contextManager.get_chatmode(chat_id)
        if not chat_mode and not event.is_tome():
            return

        request_queue = request_queues.setdefault(
            chat_id, {"texts": list(), "medias": list()}
        )
        msg_text = await gen_message(event, bot, chat_mode, request_queue["medias"])
        group_info = await bot.get_group_info(group_id=event.group_id)
        message = f'<message time="{now.isoformat()}" chatroom_name="{
            escape(group_info.get("group_name", str()))
        }" sender_id="{event.user_id}" sender_name="{
            escape(event.sender.card or event.sender.nickname or str())
        }">\n{msg_text}\n</message>'
    else:
        qqid = event.user_id
        chat_type = "private"
        chat_id = f"{qqid}.{chat_type[0]}"
        request_queue = request_queues.setdefault(
            chat_id, {"texts": list(), "medias": list()}
        )
        msg_text = await gen_message(event, bot, False, request_queue["medias"])
        message = f'<message time="{now.isoformat()}" sender_id="{qqid}" sender_name="{
            escape(event.sender.nickname)
        }">\n{msg_text}\n</message>'

    if not msg_text:
        return

    request_queue["texts"].append(message)
    times[chat_id] = event.time
    asyncio.create_task(outtime_check(bot, chat_type, qqid))


@chat_mode_on.handle()
async def _(event: GroupMessageEvent):
    if event.sender.role != "owner" and event.sender.role != "admin":
        return

    chat_id = f"{event.group_id}.g"
    await contextManager.set_chatmode(chat_id, True)
    await chat_mode_on.send("迪拉熊可以直接看到消息啦~", at_sender=True)


@chat_mode_off.handle()
async def _(event: GroupMessageEvent):
    if event.sender.role != "owner" and event.sender.role != "admin":
        return

    chat_id = f"{event.group_id}.g"
    await contextManager.set_chatmode(chat_id, False)
    await chat_mode_off.send("迪拉熊只能看到被at的消息啦~", at_sender=True)
