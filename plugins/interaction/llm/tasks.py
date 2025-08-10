import asyncio
import time
from asyncio import Task, Lock
from datetime import datetime

import anyio
import numpy as np
from nonebot.adapters.onebot.v11 import Bot
from volcenginesdkarkruntime._exceptions import ArkBadRequestError, ArkNotFoundError

from util.Config import config
from .database import contextManager
from .utils import client, system_prompt, user_prompt, prompt_hash as global_prompt_hash

OUTTIME = 10 / 2
RATE_LIMIT = 10 / 3

request_queues: dict[str, str] = dict()
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
    now = datetime.now().timestamp()
    chat_id = f"{qq_id}.{chat_type[0]}"
    if (
        chat_id not in times
        or chat_id not in request_queues
        or ((now - times[chat_id]) < OUTTIME and len(request_queues[chat_id]) <= 10)
        or (chat_id in request_queue_tasks and not request_queue_tasks[chat_id].done())
        or len(request_queues[chat_id]) <= 0
    ):
        return

    content = request_queues[chat_id]
    task = asyncio.create_task(request_queue_task(bot, chat_type, qq_id, content))
    request_queue_tasks[chat_id] = task
    del request_queues[chat_id]
    del times[chat_id]


async def request_queue_task(bot: Bot, chat_type: str, qq_id: int, content: str):
    chat_id = f"{qq_id}.{chat_type[0]}"
    context_id = await contextManager.get_latest_contextid(chat_id)

    prompt_hash = await contextManager.get_prompthash(chat_id)
    if context_id is None or prompt_hash is None or prompt_hash != global_prompt_hash:
        await api_rate_limiter.acquire()
        response = await client.context.create(
            model=config.llm_model,
            messages=[{"role": "system", "content": system_prompt}],
            extra_headers={"x-is-encrypted": "true"},
        )
        context_id = response.id
        await contextManager.set_prompthash(chat_id, global_prompt_hash)

    message = "\n".join(content)
    input_message = str.format(user_prompt, message)

    while True:
        try:
            await api_rate_limiter.acquire()
            stream = await client.context.completions.create(
                context_id=context_id,
                messages=[{"role": "user", "content": input_message}],
                model=config.llm_model,
                stream=True,
                extra_headers={"x-is-encrypted": "true"},
            )
            break
        except ArkNotFoundError:
            await contextManager.delete_latest_contextid(chat_id)
            context_id = await contextManager.get_latest_contextid(chat_id)
            if context_id is None:
                await api_rate_limiter.acquire()
                response = await client.context.create(
                    model=config.llm_model,
                    messages=[{"role": "system", "content": system_prompt}],
                    extra_headers={"x-is-encrypted": "true"},
                )
                context_id = response.id
            continue
        except ArkBadRequestError as ex:
            if ex.code == "InvalidParameter.PreviousResponseNotFound":
                await contextManager.delete_latest_contextid(chat_id)
                context_id = await contextManager.get_latest_contextid(chat_id)
                if context_id is None:
                    await api_rate_limiter.acquire()
                    response = await client.context.create(
                        model=config.llm_model,
                        messages=[{"role": "system", "content": system_prompt}],
                        extra_headers={"x-is-encrypted": "true"},
                    )
                    context_id = response.id
                continue

            if ex.code == "InvalidParameter" and ex.param == "previous_response_id":
                await api_rate_limiter.acquire()
                response = await client.context.create(
                    model=config.llm_model,
                    messages=[{"role": "system", "content": system_prompt}],
                    extra_headers={"x-is-encrypted": "true"},
                )
                context_id = response.id
                continue

            if not isinstance(ex.body, dict) or not ex.body.get(
                "message", str()
            ).startswith("Total tokens of image and text exceed max message tokens."):
                raise

            await contextManager.delete_earliest_contextid(chat_id)

    texts = list()
    async for chunk in stream:
        if chunk.id != context_id:
            context_id = chunk.id
            await contextManager.add_contextid(chat_id, context_id)

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
        if "<ignored/>" in message or len(message) <= 0:
            continue

        if chat_type == "group":
            await bot.send_group_msg(group_id=qq_id, message=message)
        elif chat_type == "private":
            await bot.send_private_msg(user_id=qq_id, message=message)

        times = rng.integers(10, 30) / 10
        await anyio.sleep(float(times))
