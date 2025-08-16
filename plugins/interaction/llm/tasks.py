import asyncio
from asyncio import Task
from datetime import datetime

import anyio
import numpy as np
from nonebot.adapters.onebot.v11 import Bot
from volcenginesdkarkruntime._exceptions import ArkBadRequestError, ArkNotFoundError

from util.config import config
from .database import contextManager
from .utils import client, system_prompt, user_prompt, prompt_hash as global_prompt_hash

OUTTIME = 10 / 2
CONTEXT_TTL = 60 * 60 * 24 * 2 / 3

request_queues: dict[str, list[str]] = dict()
response_queues: dict[str, list[str]] = dict()
request_queue_tasks: dict[str, Task] = dict()
response_queue_tasks: dict[str, Task] = dict()
times: dict[str, int] = dict()


async def outtime_check(bot: Bot, chat_type: str, qq_id: int):
    await anyio.sleep(OUTTIME)
    now = datetime.now()
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
    request_queue_tasks[chat_id] = task


async def request_queue_task(bot: Bot, chat_type: str, qq_id: int):
    chat_id = f"{qq_id}.{chat_type[0]}"
    context_id = await contextManager.get_contextid(chat_id)

    prompt_hash = await contextManager.get_prompthash(chat_id)
    if context_id is None or prompt_hash is None or prompt_hash != global_prompt_hash:
        response = await client.context.create(
            model=config.llm_model,
            messages=[{"role": "system", "content": system_prompt}],
            ttl=int(CONTEXT_TTL),
            truncation_strategy={
                "type": "rolling_tokens",
                "max_window_tokens": 4096,
                "rolling_window_tokens": 512,
            },
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

        input_message = str.format(user_prompt, message)
        try:
            stream = await client.context.completions.create(
                context_id=context_id,
                messages=[{"role": "user", "content": input_message}],
                model=config.llm_model,
                stream=True,
                extra_headers={"x-is-encrypted": "true"},
            )
            break
        except ArkNotFoundError as ex:
            print(ex)
            response = await client.context.create(
                model=config.llm_model,
                messages=[{"role": "system", "content": system_prompt}],
                extra_headers={"x-is-encrypted": "true"},
            )
            context_id = response.id
            await contextManager.set_contextid(chat_id, context_id)
        except ArkBadRequestError as ex:
            print(ex)
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
    async for chunk in stream:
        for choice in chunk.choices:
            if not choice.delta.content:
                continue

            if choice.delta.content in "\r\n":
                if len(texts) > 0:
                    reply = str().join(texts)
                    await push_and_start_sending(bot, reply, chat_type, qq_id)
                texts = list()
            else:
                texts.append(choice.delta.content)

    reply = str().join(texts)
    await push_and_start_sending(bot, reply, chat_type, qq_id)


async def push_and_start_sending(bot: Bot, reply: str, chat_type: str, qq_id: int):
    chat_id = f"{qq_id}.{chat_type[0]}"
    queue = response_queues.setdefault(chat_id, list())
    queue.append(reply)
    if chat_id not in response_queue_tasks or response_queue_tasks[chat_id].done():
        task = asyncio.create_task(response_queue_task(bot, chat_type, qq_id))
        response_queue_tasks[chat_id] = task


async def response_queue_task(bot: Bot, chat_type: str, qq_id: int):
    rng = np.random.default_rng()
    chat_id = f"{qq_id}.{chat_type[0]}"
    while len(response_queues[chat_id]) > 0:
        message = response_queues[chat_id][0]
        response_queues[chat_id].pop(0)
        if len(message.strip()) <= 0:
            continue

        if "<ignored/>" in message:
            continue

        if chat_type == "group":
            await bot.send_group_msg(group_id=qq_id, message=message)
        elif chat_type == "private":
            await bot.send_private_msg(user_id=qq_id, message=message)

        times = rng.integers(10, 30) / 10
        await anyio.sleep(float(times))
