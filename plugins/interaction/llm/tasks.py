import asyncio
import time
from asyncio import Task, Lock
from datetime import datetime

import anyio
import numpy as np
from nonebot.adapters.onebot.v11 import Bot
from openai import BadRequestError

from util.Config import config
from .database import contextManager
from .utils import client, system_prompt, user_prompt, prompt_hash as global_prompt_hash

OUTTIME = 10 / 2
RATE_LIMIT = 10 / 3

request_queues: dict[str, dict[str, list[str | dict[str, str | float]]]] = dict()
response_queues: dict[str, list[str]] = dict()
request_queue_tasks: dict[str, Task] = dict()
response_queue_tasks: dict[str, Task] = dict()
times: dict[str, int] = dict()


class RateLimiter:
    def __init__(self, max_requests_per_second: float = 1.0):
        self.max_requests_per_second = max_requests_per_second
        self.min_interval = 1.0 / max_requests_per_second
        self.last_request_time = 0.0
        self.lock = Lock()

    async def acquire(self):
        async with self.lock:
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time

            if time_since_last_request < self.min_interval:
                wait_time = self.min_interval - time_since_last_request
                await asyncio.sleep(wait_time)
                current_time = time.time()

            self.last_request_time = current_time


api_rate_limiter = RateLimiter(max_requests_per_second=RATE_LIMIT)


async def outtime_check(bot: Bot, chat_type: str, qq_id: int):
    await anyio.sleep(OUTTIME)
    chat_id = f"{qq_id}.{chat_type[0]}"
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
    task = asyncio.create_task(request_queue_task(bot, chat_type, qq_id, content))
    request_queue_tasks[chat_id] = task
    del request_queues[chat_id]
    del times[chat_id]


async def request_queue_task(
    bot: Bot,
    chat_type: str,
    qq_id: int,
    content: dict[str, list[str | dict[str, str | float]]],
):
    chat_id = f"{qq_id}.{chat_type[0]}"
    context_id = await contextManager.get_latest_contextid(chat_id)

    prompt_hash = await contextManager.get_prompthash(chat_id)
    if context_id is None or prompt_hash is None or prompt_hash != global_prompt_hash:
        await api_rate_limiter.acquire()
        response = await client.responses.create(
            input=[{"role": "system", "content": system_prompt}],
            model=config.llm_model,
            temperature=0,
            top_p=0,
            extra_body={
                "caching": {"type": "enabled"},
                "thinking": {"type": "disabled"},
            },
        )
        context_id = response.id

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
    input_message = str.format(user_prompt, message)
    input_content.append({"type": "input_text", "text": input_message})

    while True:
        try:
            await api_rate_limiter.acquire()
            stream = await client.responses.create(
                input=[{"role": "user", "content": input_content}],
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
            break
        except BadRequestError as ex:
            if ex.code == "InvalidParameter.PreviousResponseNotFound":
                await contextManager.delete_latest_contextid(chat_id)
                context_id = await contextManager.get_latest_contextid(chat_id)
                if context_id is None:
                    await api_rate_limiter.acquire()
                    response = await client.responses.create(
                        input=[{"role": "system", "content": system_prompt}],
                        model=config.llm_model,
                        temperature=0,
                        top_p=0,
                        extra_body={
                            "caching": {"type": "enabled"},
                            "thinking": {"type": "disabled"},
                        },
                    )
                    context_id = response.id
                continue

            if not ex.body.get("message", str()).startswith(
                "Total tokens of image and text exceed max message tokens."
            ):
                raise

            earliest_contextid = await contextManager.delete_earliest_contextid(chat_id)
            try:
                await client.responses.delete(earliest_contextid)
            except Exception:
                pass

    await contextManager.set_prompthash(chat_id, global_prompt_hash)
    texts = list()
    async for chunk in stream:
        if (
            hasattr(chunk, "response")
            and hasattr(chunk.response, "id")
            and chunk.response.id is not None
            and chunk.response.id != context_id
        ):
            await contextManager.add_contextid(chat_id, chunk.response.id)

        if not hasattr(chunk, "delta") or not chunk.delta:
            continue

        if chunk.delta in "\r\n":
            if len(texts) > 0:
                reply = str().join(texts)
                await push_and_start_sending(bot, reply, chat_type, qq_id)
            texts = list()
        else:
            texts.append(chunk.delta)

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
        if "<ignored/>" in message or len(message) <= 0:
            continue

        if chat_type == "group":
            await bot.send_group_msg(group_id=qq_id, message=message)
        elif chat_type == "private":
            await bot.send_private_msg(user_id=qq_id, message=message)

        times = rng.integers(10, 30) / 10
        await anyio.sleep(float(times))
