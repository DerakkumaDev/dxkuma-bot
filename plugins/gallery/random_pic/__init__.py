import asyncio
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiofiles
from PIL import Image, UnidentifiedImageError
from nonebot import on_regex
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageSegment
from numpy import random
from xxhash import xxh32_hexdigest

from util.config import config
from util.exceptions import SkipedException
from util.lock import locks
from util.stars import stars
from ..rank.database import ranking

rand_pic = on_regex(r"^(随机)?(迪拉熊|dlx)((涩|色|瑟)图|st)?$", re.I)

LIMIT_MINUTES = 2
LIMIT_TIMES = 6

groups: dict[int, list[datetime]] = dict()


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
    now = datetime.fromtimestamp(event.time, timezone(timedelta(hours=8)))
    if type == "nsfw":
        if event.self_id not in config.nsfw_allowed:
            key = xxh32_hexdigest(f"{event.time}_{event.group_id}_{event.real_seq}")
            if key in locks and locks[key].count > 1:
                raise SkipedException
            await rand_pic.finish(
                (
                    MessageSegment.text("迪拉熊不准你看！"),
                    MessageSegment.image(Path("./Static/Gallery/0.png")),
                )
            )
        if os.path.exists("./data/nsfw_lock"):
            await rand_pic.finish("由于账号被警告，这个功能暂时无法使用了mai~")
    elif group_id != config.special_group:  # 不被限制的 group_id
        while len(groups[group_id]) > 0:
            t = groups[group_id][0]
            if now - t < timedelta(minutes=LIMIT_MINUTES):
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
    star, method, extend = await stars.give_rewards(
        qq, 5, 25, "欣赏迪拉熊美图", event.time
    )
    msg = f"迪拉熊奖励你{star}颗★mai~"
    if method & 0b0001:
        msg += f"人品大爆发，迪拉熊额外送你{extend}颗★哦~"
    if method & 0b1_0000:
        msg += f"今日首次奖励，迪拉熊额外送你{extend}颗★哦~"
    await rand_pic.send(msg, at_sender=True)
    if type == "nsfw":
        msg_id = send_msg["message_id"]

        async def delete_msg_after_delay():
            await asyncio.sleep(10)
            await bot.delete_msg(message_id=msg_id)

        asyncio.create_task(delete_msg_after_delay())
