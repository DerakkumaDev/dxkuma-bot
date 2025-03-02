import os
import traceback
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from aiohttp import ClientError
from nonebot import get_bot
from nonebot.adapters.onebot.v11 import MessageSegment, Event, MessageEvent
from nonebot.adapters.onebot.v11.exception import OneBotV11AdapterException
from nonebot.internal.matcher import Matcher
from nonebot.message import run_postprocessor
from numpy import random

from util.Config import config
from util.exceptions import NotAllowedException, NeedToSwitchException

rng = random.default_rng()

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
    if not exception or isinstance(
        exception,
        (
            OneBotV11AdapterException,
            ClientError,
            NotAllowedException,
            NeedToSwitchException,
        ),
    ):
        return
    bot = get_bot()
    trace = "".join(traceback.format_exception(exception)).replace("\\n", "\r\n")
    msg = MessageSegment.text(
        f"{trace}{event.get_plaintext() if isinstance(event, MessageEvent) else event.get_type()}\r\n{event.get_session_id()}"
    )
    await bot.send_msg(group_id=config.dev_group, message=msg)
    path = PICPATH
    files = os.listdir(path)
    if not files:
        feedback = (
            MessageSegment.text("（迪拉熊出了点问题）"),
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
            MessageSegment.text("（迪拉熊出了点问题）"),
            MessageSegment.image(Path("./Static/Help/pleasewait.png")),
        )
        await matcher.finish(feedback)
    with open(pic_path, "rb") as fd:
        feedback = (
            MessageSegment.text("迪拉熊出了点问题，来点迪拉熊吧"),
            MessageSegment.image(fd.read()),
        )
        await matcher.send(feedback)
