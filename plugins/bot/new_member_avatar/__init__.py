import shelve
from io import BytesIO

import aiohttp
from PIL import Image, ImageDraw
from dill import Pickler, Unpickler
from nonebot import on_startswith, on_message
from nonebot.adapters.onebot.v11 import MessageSegment, GroupMessageEvent
from nonebot.rule import to_me

shelve.Pickler = Pickler
shelve.Unpickler = Unpickler

avatar = on_startswith("旅行伙伴加入", to_me())
avatar_img_msg = on_message(block=False)


async def gen_avatar(pic: bytes) -> bytes:
    img = Image.open(BytesIO(pic))
    width, height = img.size
    if width > height:
        img = img.crop(
            (
                int(width / 2 - height / 2),
                0,
                int(width / 2 + height / 2),
                height,
            )
        )
    elif height > width:
        img = img.crop(
            (
                0,
                int(height / 2 - width / 2),
                width,
                int(height / 2 + width / 2),
            )
        )

    img = img.resize((720, 720), Image.Resampling.LANCZOS)

    circle_mask = Image.new("L", (720, 720), 0)
    draw = ImageDraw.Draw(circle_mask)
    draw.circle((360, 360), 362, 255)

    frame = Image.open("./Static/NewMemberAvatar/0.png")
    avatar_img = Image.new("RGBA", frame.size)
    avatar_img.paste(img, (237, 240), circle_mask)
    avatar_img.paste(frame, (0, 0), frame)

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
        with shelve.open("./data/gen_avatar.db") as data:
            key = str(hash(f"{event.group_id}{event.user_id}"))
            if key in data:
                data[key] = event.time
                return

            data.setdefault(key, event.time)
        return

    await avatar.send(
        (
            MessageSegment.at(event.user_id),
            MessageSegment.text("迪拉熊绘制中，稍等一下mai~"),
        )
    )
    msg = MessageSegment.at(event.user_id)

    for pic_url in pic_urls:
        async with aiohttp.ClientSession() as session:
            async with session.get(pic_url) as resp:
                icon = await resp.read()

        img_bytes = await gen_avatar(icon)

        msg += (MessageSegment.image(img_bytes),)

    await avatar.send(msg)


@avatar_img_msg.handle()
async def _(event: GroupMessageEvent):
    pic_urls = list()
    for seg in event.get_message():
        if seg.type != "image":
            continue

        pic_urls.append(seg.data["url"])

    if len(pic_urls) <= 0:
        return

    with shelve.open("./data/gen_avatar.db") as data:
        key = str(hash(f"{event.group_id}{event.user_id}"))
        if key not in data:
            return

        if event.time - data[key] >= 15:
            data.pop(key)
            return

        data.pop(key)

    await avatar.send(
        (
            MessageSegment.at(event.user_id),
            MessageSegment.text("迪拉熊绘制中，稍等一下mai~"),
        )
    )
    msg = MessageSegment.at(event.user_id)

    for pic_url in pic_urls:
        async with aiohttp.ClientSession() as session:
            async with session.get(pic_url) as resp:
                icon = await resp.read()

        img_bytes = await gen_avatar(icon)

        msg += (MessageSegment.image(img_bytes),)

    await avatar.send(msg)
