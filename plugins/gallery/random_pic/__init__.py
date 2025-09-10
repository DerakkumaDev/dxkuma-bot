import asyncio
import datetime
import os
import re
from pathlib import Path

import aiofiles
from PIL import Image, UnidentifiedImageError
from nonebot import on_regex
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageSegment
from numpy import random

from util.config import config
from .rule import nsfw
from ..rank.database import ranking

rand_pic = on_regex(r"^(随机)?(迪拉熊|dlx)((涩|色|瑟)图|st)?$", re.I, nsfw())

LIMIT_MINUTES = 1
LIMIT_TIMES = 10

groups: dict[int, list[datetime.datetime]] = dict()


def check_image(imgpath: Path | str):
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


@rand_pic.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    rng = random.default_rng()
    group_id = event.group_id
    qq = event.get_user_id()
    msg = event.get_plaintext()
    type = "sfw"
    path = ranking.pic_path
    groups.setdefault(group_id, list())
    if re.search(r"(涩|色|瑟)图|st", msg, re.I):
        type = "nsfw"
        path = ranking.nsfw_pic_path
    files = os.listdir(path)
    if not files:
        msg = (
            MessageSegment.text("迪拉熊不准你看！"),
            MessageSegment.image(Path("./Static/Gallery/0.png")),
        )
        await rand_pic.finish(msg)
    for _ in range(3):
        file = rng.choice(files)
        pic_path = os.path.join(path, file)
        if check_image(pic_path):
            break
    else:
        msg = (
            MessageSegment.text("迪拉熊不准你看！"),
            MessageSegment.image(Path("./Static/Gallery/0.png")),
        )
        await rand_pic.finish(msg)
    now = datetime.datetime.fromtimestamp(event.time)
    if type == "nsfw":
        if os.path.exists("./data/nsfw_lock"):
            await rand_pic.finish("由于账号被警告，这个功能暂时无法使用了mai~")
    elif group_id != config.special_group:  # 不被限制的 group_id
        while len(groups[group_id]) > 0:
            t = groups[group_id][0]
            if now - t < datetime.timedelta(minutes=LIMIT_MINUTES):
                break
            groups[group_id].pop(0)
        if len(groups[group_id]) >= LIMIT_TIMES:
            if type == "sfw":
                msg = MessageSegment.text(
                    "迪拉熊提醒你：注意不要过度刷屏，给别人带来困扰mai~再试一下吧~"
                )
            elif type == "nsfw":
                msg = MessageSegment.text(
                    "哼哼，迪拉熊的魅力这么大嘛，但是也要注意节制mai~"
                )
            await rand_pic.finish(msg)
    async with aiofiles.open(pic_path, "rb") as fd:
        send_msg = await rand_pic.send(MessageSegment.image(await fd.read()))
    groups[group_id].append(now)
    await ranking.update_count(qq=qq, type=type)
    if type == "nsfw":
        msg_id = send_msg["message_id"]

        async def delete_msg_after_delay():
            await asyncio.sleep(10)
            await bot.delete_msg(message_id=msg_id)

        asyncio.create_task(delete_msg_after_delay())
