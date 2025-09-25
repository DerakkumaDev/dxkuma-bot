import asyncio
import traceback
from asyncio import Task
from datetime import datetime, timedelta, timezone

import numpy as np
from nonebot import get_bot
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.exception import AdapterException
from volcenginesdkarkruntime._exceptions import ArkBadRequestError, ArkNotFoundError

from util.config import config
from .database import contextManager
from .utils import client, prompt_hash as global_prompt_hash, system_prompt

OUTTIME = 10 / 2

request_queues: dict[str, list[str]] = dict()
response_queues: dict[str, list[str]] = dict()
request_queue_tasks: dict[str, Task] = dict()
response_queue_tasks: dict[str, Task] = dict()
times: dict[str, int] = dict()


async def outtime_check(bot: Bot, chat_type: str, qq_id: int):
    await asyncio.sleep(OUTTIME)
    now = datetime.now(timezone(timedelta(hours=8)))
    chat_id = f"{qq_id}.{chat_type[0]}"
    if chat_id in request_queue_tasks and not request_queue_tasks[chat_id].done():
        return

    if chat_id not in request_queues:
        return

    message_count = len(request_queues[chat_id])
    if message_count <= 0:
        return

    if chat_id not in times:
        return

    if (now.timestamp() - times[chat_id]) < OUTTIME and message_count <= 10:
        return

    task = asyncio.create_task(request_queue_task(bot, chat_type, qq_id))
    task.add_done_callback(on_done)
    request_queue_tasks[chat_id] = task


async def request_queue_task(bot: Bot, chat_type: str, qq_id: int):
    chat_id = f"{qq_id}.{chat_type[0]}"
    context_id = await contextManager.get_contextid(chat_id)

    prompt_hash = await contextManager.get_prompthash(chat_id)
    if context_id is None or prompt_hash is None or prompt_hash != global_prompt_hash:
        response = await client.context.create(
            model=config.llm_model,
            messages=[{"role": "system", "content": system_prompt}],
            extra_headers={"x-is-encrypted": "true"},
        )
        context_id = response.id
        await contextManager.set_contextid(chat_id, context_id)
        await contextManager.set_prompthash(chat_id, global_prompt_hash)

    message = str()
    while True:
        if chat_id in request_queues:
            while (count := len(request_queues[chat_id])) > 0:
                message += request_queues[chat_id].pop(0)
                if count > 1:
                    message += "\n"

        try:
            stream = await client.context.completions.create(
                context_id=context_id,
                messages=[{"role": "user", "content": message}],
                model=config.llm_model,
                stream=True,
                extra_headers={"x-is-encrypted": "true"},
            )
            break
        except ArkNotFoundError:
            response = await client.context.create(
                model=config.llm_model,
                messages=[{"role": "system", "content": system_prompt}],
                extra_headers={"x-is-encrypted": "true"},
            )
            context_id = response.id
            await contextManager.set_contextid(chat_id, context_id)
        except ArkBadRequestError as ex:
            await exception_report(ex)
            if ex.code == "InvalidParameter.PreviousResponseNotFound":
                response = await client.context.create(
                    model=config.llm_model,
                    messages=[{"role": "system", "content": system_prompt}],
                    extra_headers={"x-is-encrypted": "true"},
                )
                context_id = response.id
                await contextManager.set_contextid(chat_id, context_id)
                continue

            if ex.code == "InvalidParameter" and ex.param == "previous_response_id":
                response = await client.context.create(
                    model=config.llm_model,
                    messages=[{"role": "system", "content": system_prompt}],
                    extra_headers={"x-is-encrypted": "true"},
                )
                context_id = response.id
                await contextManager.set_contextid(chat_id, context_id)
                continue

            raise

    texts = list()
    level = 0
    async for chunk in stream:
        for choice in chunk.choices:
            if not choice.delta.content:
                continue

            texts_count = len(texts)
            if choice.delta.content in "\r\n":
                if texts_count > 0:
                    reply = str().join(texts)
                    await push_and_start_sending(bot, reply, chat_type, qq_id, level)
                texts = list()
            elif choice.delta.content == "，":
                if texts_count <= 0:
                    continue
                reply = str().join(texts)
                if len(reply) <= 5:
                    texts.append(choice.delta.content)
                    continue
                await push_and_start_sending(bot, reply, chat_type, qq_id, level)
                texts = list()
            elif choice.delta.content == "（":
                if texts_count > 0:
                    reply = str().join(texts)
                    await push_and_start_sending(bot, reply, chat_type, qq_id, level)
                    texts = list()
                level += 1
                texts.append(choice.delta.content)
            elif choice.delta.content == "）":
                texts.append(choice.delta.content)
                reply = str().join(texts)
                await push_and_start_sending(bot, reply, chat_type, qq_id, level)
                level -= 1
                texts = list()
            elif (
                choice.delta.content in "~？！"
                and texts_count > 0
                and texts[-1] == "mai"
            ):
                if texts_count >= 2 and texts[-2] in "，。？！":
                    texts.pop(-2)
                texts.append(choice.delta.content)
                reply = str().join(texts)
                await push_and_start_sending(bot, reply, chat_type, qq_id, level)
                texts = list()
            elif choice.delta.content in "。？！" and len(texts) <= 0:
                continue
            else:
                texts.append(choice.delta.content)

    reply = str().join(texts)
    await push_and_start_sending(bot, reply, chat_type, qq_id, level)


async def push_and_start_sending(
    bot: Bot, reply: str, chat_type: str, qq_id: int, level: int
):
    reply = reply.strip()
    if len(reply) <= 0 or (len(reply) == 4 and reply[:3] == "mai"):
        return
    if level > 0:
        if not reply.startswith("（"):
            reply = f"（{reply}"
        if not reply.endswith("）"):
            reply += "）"
    elif reply[-4:-1] != "mai":
        start = reply[:-1]
        end = reply[-1]
        if end in "，。":
            end = "~"
        elif end == "…" and start.endswith("…"):
            start = start[:-1]
            end = "……"
        elif end not in "？！":
            end = "~"
            start = reply
        reply = f"{start}mai{end}"
    chat_id = f"{qq_id}.{chat_type[0]}"
    queue = response_queues.setdefault(chat_id, list())
    queue.append(reply)
    if chat_id not in response_queue_tasks or response_queue_tasks[chat_id].done():
        task = asyncio.create_task(response_queue_task(bot, chat_type, qq_id))
        task.add_done_callback(on_done)
        response_queue_tasks[chat_id] = task


async def response_queue_task(bot: Bot, chat_type: str, qq_id: int):
    rng = np.random.default_rng()
    chat_id = f"{qq_id}.{chat_type[0]}"
    while len(response_queues[chat_id]) > 0:
        message = response_queues[chat_id][0]
        response_queues[chat_id].pop(0)
        if chat_type == "group":
            await bot.send_group_msg(group_id=qq_id, message=message)
        elif chat_type == "private":
            await bot.send_private_msg(user_id=qq_id, message=message)

        times = rng.integers(10, 30) / 10
        await asyncio.sleep(float(times))


def on_done(task: Task):
    if not (exception := task.exception()) or isinstance(exception, AdapterException):
        return

    asyncio.run(exception_report(exception))


async def exception_report(ex):
    bot = get_bot()
    trace = str().join(traceback.format_exception(ex)).replace("\\n", "\r\n")
    msg = MessageSegment.text(trace)
    await bot.send_msg(group_id=config.dev_group, message=msg)
