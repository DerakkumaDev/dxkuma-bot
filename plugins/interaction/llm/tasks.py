import asyncio
from asyncio import Task
from datetime import datetime

import anyio
from nonebot import get_bot
from openai import NOT_GIVEN

from util.Config import config
from .database import contextManager
from .utils import client

OUTTIME = 10 / 3

request_queues: dict[str, dict[str, list[str]]] = dict()
response_queues: dict[str, list[str]] = dict()
request_queue_tasks: dict[str, Task] = dict()
response_queue_tasks: dict[str, Task] = dict()
times: dict[str, int] = dict()


async def outtime_check(
    chat_id: str, chat_type: str, qq_id: int, chat_mode: bool = False
):
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
        request_queue_task(chat_id, chat_type, qq_id, content, chat_mode)
    )
    request_queue_tasks[chat_id] = task


async def request_queue_task(
    chat_id: str,
    chat_type: str,
    qq_id: int,
    content: dict[str, list[str]],
    chat_mode: bool,
):
    context_id = contextManager.get_contextid(chat_id)
    input_content = list()
    for image_url in content["images"]:
        input_content.append(
            {"type": "input_image", "detail": "high", "image_url": image_url}
        )

    message = "\n".join(content["texts"])
    if chat_mode:
        message = str.format(config.llm_user_prompt, message)

    input_content.append({"type": "input_text", "text": message})
    input = [{"role": "user", "content": input_content}]
    if context_id is NOT_GIVEN:
        input.insert(0, {"role": "system", "content": config.llm_system_prompt})

    stream = await client.responses.create(
        model=config.llm_model,
        input=input,
        previous_response_id=context_id,
        stream=True,
        extra_body={
            "caching": {"type": "enabled"},
            "thinking": {"type": "disabled"},
        },
    )

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

        if chunk.delta == "。":
            reply = str().join(texts)
            await push_and_start_sending(chat_id, reply, chat_type, qq_id)
            texts.clear()
        elif chunk.delta in "\r\n":
            if len(texts) > 0:
                reply = str().join(texts)
                await push_and_start_sending(chat_id, reply, chat_type, qq_id)
            texts.clear()
        elif chunk.delta == "（" and len(texts) > 0:
            reply = str().join(texts)
            await push_and_start_sending(chat_id, reply, chat_type, qq_id)
            texts.clear()
            texts.append(chunk.delta)
        elif chunk.delta in "）！？" or (chunk.delta == "~" and texts[-1] == "mai"):
            texts.append(chunk.delta)
            reply = str().join(texts)
            await push_and_start_sending(chat_id, reply, chat_type, qq_id)
            texts.clear()
        else:
            texts.append(chunk.delta)

    reply = str().join(texts)
    await push_and_start_sending(chat_id, reply, chat_type, qq_id)


async def push_and_start_sending(chat_id: str, reply: str, chat_type: str, qq_id: int):
    queue = response_queues.setdefault(chat_id, list())
    queue.append(reply)
    if chat_id not in response_queue_tasks or response_queue_tasks[chat_id].done():
        task = asyncio.create_task(response_queue_task(chat_id, chat_type, qq_id))
        response_queue_tasks[chat_id] = task


async def response_queue_task(chat_id: str, chat_type: str, qq_id: int):
    while len(response_queues[chat_id]) > 0:
        sender = get_bot()
        message = response_queues[chat_id][0]
        response_queues[chat_id].pop(0)
        if "<ignored/>" in message or len(message) <= 0:
            continue

        if chat_type == "group":
            await sender.send_group_msg(group_id=qq_id, message=message)
        elif chat_type == "private":
            await sender.send_private_msg(user_id=qq_id, message=message)

        await anyio.sleep(2)
