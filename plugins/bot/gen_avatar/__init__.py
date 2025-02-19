import math
import os
import re
import shelve
from io import BytesIO
from pathlib import Path

import aiohttp
from PIL import Image, ImageDraw
from dill import Pickler, Unpickler
from nonebot import on_regex
from nonebot.adapters.onebot.v11 import MessageSegment, GroupMessageEvent
from nonebot.rule import to_me

shelve.Pickler = Pickler
shelve.Unpickler = Unpickler

avatar = on_regex(r"^(旅行伙伴加入|相框\d+)", rule=to_me())


def gen_avatar(pic: bytes, id) -> bytes:
    img = Image.open(BytesIO(pic))
    width, height = img.size
    if width > height:
        img = img.crop(
            (
                math.ceil(width / 2 - height / 2),
                0,
                math.ceil(width / 2 + height / 2),
                height,
            )
        )
    elif height > width:
        img = img.crop(
            (
                0,
                math.ceil(height / 2 - width / 2),
                width,
                math.ceil(height / 2 + width / 2),
            )
        )

    img = img.resize((720, 720), Image.Resampling.LANCZOS)

    if id == "0":
        circle_mask = Image.new("L", (720, 720), 0)
        draw = ImageDraw.Draw(circle_mask)
        draw.circle((360, 360), 362, 255)

        frame = Image.open("./Static/GenAvatar/0.png")
        avatar_img = Image.new("RGBA", frame.size)
        avatar_img.paste(img, (237, 240), circle_mask)
        avatar_img.paste(frame, (0, 0), frame)
    else:
        frame = Image.open(f"./Static/GenAvatar/{id}.png")
        frame = frame.resize((720, 720), Image.Resampling.LANCZOS)
        avatar_img = Image.alpha_composite(img, frame)

    img_byte_arr = BytesIO()
    avatar_img.save(img_byte_arr, format="PNG", optimize=True)
    img_byte_arr.seek(0)
    img_bytes = img_byte_arr.getvalue()

    return img_bytes


@avatar.handle()
async def _(event: GroupMessageEvent):
    pic_urls = list()
    for seg in event.get_message():
        if seg.type != "image":
            continue

        pic_urls.append(seg.data["url"])
    if event.reply:
        for seg in event.reply.message:
            if seg.type != "image":
                continue

            pic_urls.append(seg.data["url"])

    if len(pic_urls) <= 0:
        return

    index = re.search(r"\d+", event.get_plaintext())
    if index:
        id = index.group()
    else:
        id = "0"

    if not os.path.exists(f"./Static/GenAvatar/{id}.png"):
        msg = (
            MessageSegment.at(event.user_id),
            MessageSegment.text(" "),
            MessageSegment.text("迪拉熊没有找到合适的背景"),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await avatar.finish(msg)

    await avatar.send(
        (
            MessageSegment.at(event.user_id),
            MessageSegment.text(" "),
            MessageSegment.text("迪拉熊绘制中，稍等一下mai~"),
        )
    )
    msg = (
        MessageSegment.at(event.user_id),
        MessageSegment.text(" "),
    )

    for pic_url in pic_urls:
        async with aiohttp.ClientSession() as session:
            async with session.get(pic_url) as resp:
                icon = await resp.read()

        img_bytes = gen_avatar(icon, id)

        msg += (MessageSegment.image(img_bytes),)

    await avatar.send(msg)
