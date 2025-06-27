import os
import traceback
from dbm import error
from pathlib import Path

import aiofiles
from PIL import Image, UnidentifiedImageError
from aiohttp import ClientError
from nonebot import get_bot
from nonebot.adapters.onebot.v11 import MessageSegment, Event, MessageEvent
from nonebot.adapters.onebot.v11.exception import OneBotV11AdapterException
from nonebot.internal.matcher import Matcher
from nonebot.message import run_postprocessor
from numpy import random
from starlette.websockets import WebSocketDisconnect

from util.Config import config
from util.exceptions import NotAllowedException, NeedToSwitchException

PICPATH = "./Static/Gallery/SFW/"


def check_image(imgpath: Path):
    try:
        image = Image.open(imgpath)
    except UnidentifiedImageError:
        return False
    try:
        image.verify()
    except OSError:
        return False
    image.close()
    return True


@run_postprocessor
async def _(event: Event, matcher: Matcher, exception: Exception | None):
    rng = random.default_rng()
    if not exception or isinstance(
        exception,
        (
            OneBotV11AdapterException,
            WebSocketDisconnect,
            ClientError,
            NotAllowedException,
            NeedToSwitchException,
            error[0],
        ),
    ):
        return
    bot = get_bot()
    trace = "".join(traceback.format_exception(exception)).replace("\\n", "\r\n")
    msg = MessageSegment.text(
        f"{trace}{event.get_message().extract_plain_text() if isinstance(event, MessageEvent) else event.get_type()}\r\n{event.get_session_id()}"
    )
    await bot.send_msg(group_id=config.dev_group, message=msg)
    path = PICPATH
    files = os.listdir(path)
    if not files:
        feedback = (
            MessageSegment.text("（迪拉熊遇到了一点小问题）"),
            MessageSegment.image(Path("./Static/Help/pleasewait.png")),
        )
        await matcher.finish(feedback)
    for _ in range(3):
        file = rng.choice(files)
        pic_path = os.path.join(path, file)
        if check_image(pic_path):
            break
    else:
        feedback = (
            MessageSegment.text("（迪拉熊遇到了一点小问题）"),
            MessageSegment.image(Path("./Static/Help/pleasewait.png")),
        )
        await matcher.finish(feedback)
    async with aiofiles.open(pic_path, "rb") as fd:
        feedback = (
            MessageSegment.text("迪拉熊遇到了一点小问题，先来看点迪拉熊吧"),
            MessageSegment.image(await fd.read()),
        )
        await matcher.send(feedback)
