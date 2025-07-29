from datetime import datetime

from anyio import Lock
from anyio.to_thread import run_sync
from nonebot import on_message, on_regex
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageEvent,
    GroupMessageEvent,
)
from openai import NOT_GIVEN

from util.Config import config
from .database import contextManager
from .utils import client, escape, gen_message, locks

handler = on_message(priority=10000, block=False)

chat_mode_on = on_regex(r"^((开启|开始|启用|启动|打开)聊天(模式)?|(迪拉熊|dlx)说话?)$")
chat_mode_off = on_regex(r"^((关闭|禁用|结束)聊天(模式)?|(迪拉熊|dlx)闭嘴?)$")


@handler.handle()
async def _(bot: Bot, event: MessageEvent):
    now = datetime.fromtimestamp(event.time)
    if isinstance(event, GroupMessageEvent):
        chat_id = f"{event.group_id}.g"
        chat_mode = contextManager.get_chatmode(chat_id)
        if not chat_mode and not event.is_tome():
            return

        user_name = event.sender.card or event.sender.nickname or str()
        msg_text, image_urls = await gen_message(event, bot, chat_mode)
        group_name = (await bot.get_group_info(group_id=event.group_id))["group_name"]
        message = f'<message time="{now.isoformat()}" chatroom_name="{escape(group_name)}" sender_id="{event.get_user_id()}" sender_name="{escape(user_name)}">\n{msg_text}\n</message>'
        message = str.format(config.llm_user_prompt, message) if chat_mode else message
    else:
        chat_id = f"{event.get_user_id()}.p"
        user_name = event.sender.nickname
        msg_text, image_urls = await gen_message(event, bot, True)
        message = f'<message time="{now.isoformat()}" sender_id="{event.get_user_id()}" sender_name="{escape(user_name)}">\n{msg_text}\n</message>'

    if not msg_text:
        return

    content = list()

    for image_url in image_urls:
        content.append(
            {"type": "input_image", "detail": "high", "image_url": image_url}
        )

    content.append({"type": "input_text", "text": message})

    input = [{"role": "user", "content": content}]

    async with locks.setdefault(chat_id, Lock()):
        context_id = contextManager.get_contextid(chat_id)
        if context_id is None:
            input.insert(0, {"role": "system", "content": config.llm_system_prompt})

        response = await run_sync(
            lambda: client.responses.create(
                model=config.llm_model,
                input=input,
                previous_response_id=NOT_GIVEN if context_id is None else context_id,
                extra_body={
                    "caching": {"type": "enabled"},
                    "thinking": {"type": "disabled"},
                },
            )
        )
        contextManager.set_contextid(chat_id, response.id)

    reply = response.output_text
    if reply == "<ignored/>":
        return

    await handler.send(reply)


@chat_mode_on.handle()
async def _(event: GroupMessageEvent):
    if event.sender.role != "owner" and event.sender.role != "admin":
        return

    chat_id = f"{event.group_id}.g"
    contextManager.set_chatmode(chat_id, True)
    await chat_mode_on.send("迪拉熊帮你换好啦~", at_sender=True)


@chat_mode_off.handle()
async def _(event: GroupMessageEvent):
    if event.sender.role != "owner" and event.sender.role != "admin":
        return

    chat_id = f"{event.group_id}.g"
    contextManager.set_chatmode(chat_id, False)
    await chat_mode_on.send("迪拉熊帮你换好啦~", at_sender=True)
