import asyncio
from asyncio import Task
from datetime import datetime

import anyio
import numpy as np
from nonebot.adapters.onebot.v11 import Bot
from openai import NOT_GIVEN

from util.Config import config
from .database import contextManager
from .utils import client, system_prompt, user_prompt, prompt_hash as global_prompt_hash

OUTTIME = 10 / 3

request_queues: dict[str, dict[str, list[str | dict[str, str | float]]]] = dict()
response_queues: dict[str, list[str]] = dict()
request_queue_tasks: dict[str, Task] = dict()
response_queue_tasks: dict[str, Task] = dict()
times: dict[str, int] = dict()


async def outtime_check(bot: Bot, chat_id: str, chat_type: str, qq_id: int):
    await anyio.sleep(OUTTIME)
    if (
        chat_id not in times
        or (
            (datetime.now().timestamp() - times[chat_id]) < OUTTIME
            and len(request_queues[chat_id]) <= 10
        )
        or (chat_id in request_queue_tasks and not request_queue_tasks[chat_id].done())
        or chat_id not in request_queues
        or len(request_queues[chat_id]) <= 0
    ):
        return

    content = request_queues[chat_id]
    del request_queues[chat_id]
    del times[chat_id]
    task = asyncio.create_task(
        request_queue_task(bot, chat_id, chat_type, qq_id, content)
    )
    request_queue_tasks[chat_id] = task


async def request_queue_task(
    bot: Bot,
    chat_id: str,
    chat_type: str,
    qq_id: int,
    content: dict[str, list[str | dict[str, str | float]]],
):
    context_id = contextManager.get_contextid(chat_id)
    input_content = list()

    for media in content["medias"]:
        media_info = {
            "type": f"input_{media['type']}",
            f"{media['type']}_url": media["url"],
        }
        if media["type"] == "vedio":
            media_info["fps"] = 2 / 10

        input_content.append(media_info)

    message = "\n".join(content["texts"])
    message = str.format(user_prompt, message)

    input_content.append({"type": "input_text", "text": message})
    input = [{"role": "user", "content": input_content}]
    prompt_hash = contextManager.get_prompthash(chat_id)
    if prompt_hash is None or prompt_hash != global_prompt_hash:
        context_id = NOT_GIVEN
        input.insert(0, {"role": "system", "content": system_prompt})

    stream = await client.responses.create(
        input=input,
        model=config.llm_model,
        previous_response_id=context_id,
        stream=True,
        temperature=2 / 2,
        top_p=2 / 3,
        extra_body={
            "caching": {"type": "enabled"},
            "thinking": {"type": "disabled"},
        },
    )

    contextManager.set_prompthash(chat_id, global_prompt_hash)
    texts = list()
    async for chunk in stream:
        if (
            hasattr(chunk, "response")
            and hasattr(chunk.response, "id")
            and chunk.response.id is not None
            and chunk.response.id != context_id
        ):
            contextManager.set_contextid(chat_id, chunk.response.id)

        if not hasattr(chunk, "delta") or not chunk.delta:
            continue

        if chunk.delta in "\r\n":
            if len(texts) > 0:
                reply = str().join(texts)
                await push_and_start_sending(bot, chat_id, reply, chat_type, qq_id)
            texts = list()
        else:
            texts.append(chunk.delta)

    reply = str().join(texts)
    await push_and_start_sending(bot, chat_id, reply, chat_type, qq_id)


async def push_and_start_sending(
    bot: Bot, chat_id: str, reply: str, chat_type: str, qq_id: int
):
    queue = response_queues.setdefault(chat_id, list())
    queue.append(reply)
    if chat_id not in response_queue_tasks or response_queue_tasks[chat_id].done():
        task = asyncio.create_task(response_queue_task(bot, chat_id, chat_type, qq_id))
        response_queue_tasks[chat_id] = task


async def response_queue_task(bot: Bot, chat_id: str, chat_type: str, qq_id: int):
    rng = np.random.default_rng()
    while len(response_queues[chat_id]) > 0:
        message = response_queues[chat_id][0]
        response_queues[chat_id].pop(0)
        if "<ignored/>" in message or len(message) <= 0:
            continue

        if chat_type == "group":
            await bot.send_group_msg(group_id=qq_id, message=message)
        elif chat_type == "private":
            await bot.send_private_msg(user_id=qq_id, message=message)

        times = rng.integers(10, 30) / 10
        await anyio.sleep(float(times))
