import re
from pathlib import Path

from nonebot import on_fullmatch, on_regex
from nonebot.adapters.onebot.v11 import Bot, MessageSegment, GroupMessageEvent
from nonebot.rule import to_me
from numpy import random

from plugins.bot.concurrent_lock.util import locks
from util.Config import config
from util.exceptions import NeedToSwitchException

xc = on_regex(r"^(香草|想草|xc)(迪拉熊|dlx)$", re.I)
wxhn = on_regex(r"^(迪拉熊|dlx)我喜欢你$", re.I)
roll = on_regex(r"是.+还是.", rule=to_me())
cum = on_fullmatch("dlxcum", ignorecase=True)
eatbreak = on_regex(r"绝赞(给|请)你吃|(给|请)你吃绝赞", rule=to_me())

conversations = {
    1: "变态！！！",
    2: "走开！！！",
    3: "不要靠近迪拉熊！！！",
    4: "迪拉熊不和你玩了！",
    5: "小心迪拉熊吃你绝赞！",
    6: "小心迪拉熊吃你星星！",
    7: "你不可以这样对迪拉熊！",
    8: "迪拉熊不想理你了，哼！",
    9: "不把白潘AP了就别想！",
    10: "……你会对迪拉熊负责的，对吧？",
}


@xc.handle()
async def _(event: GroupMessageEvent):
    rng = random.default_rng()
    weights = [0.11, 0.11, 0.11, 0.11, 0.11, 0.11, 0.11, 0.11, 0.11, 0.01]
    ran_number = rng.choice(range(1, 11), p=weights)
    text = conversations[ran_number]
    if ran_number == 10:
        pic_path = "./Static/WannaCao/1.png"
    else:
        pic_path = "./Static/WannaCao/0.png"
    msg = (MessageSegment.text(text), MessageSegment.image(Path(pic_path)))
    await xc.send(msg)


@wxhn.handle()
async def _(event: GroupMessageEvent):
    msg = (
        MessageSegment.text("迪拉熊也喜欢你mai~❤️"),
        MessageSegment.image(Path("./Static/LikeYou/0.png")),
    )
    await wxhn.send(msg, at_sender=True)


@roll.handle()
async def _(event: GroupMessageEvent):
    rng = random.default_rng()
    text = event.get_plaintext()
    roll_list = re.findall(r"(?<=是)(.+?)(?=还|$)", text)
    if not roll_list:
        msg = (
            MessageSegment.text("没有选项要让迪拉熊怎么选嘛~"),
            MessageSegment.image(Path("./Static/Roll/1.png")),
        )
        await roll.finish(msg, at_sender=True)
    if len(set(roll_list)) == 1:
        msg = (
            MessageSegment.text("就一个选项要让迪拉熊怎么选嘛~"),
            MessageSegment.image(Path("./Static/Roll/1.png")),
        )
        await roll.finish(msg, at_sender=True)
    output = rng.choice(roll_list)
    msg = (
        MessageSegment.text(f"迪拉熊建议你选择“{output}”呢~"),
        MessageSegment.image(Path("./Static/Roll/0.png")),
    )
    await roll.send(msg, at_sender=True)


@cum.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    rng = random.default_rng()
    key = hash(f"{event.group_id}{event.user_id}{event.time}")
    if (
        key in locks
        and locks[key].count > 1
        and bot.self_id not in config.allowed_accounts
    ):
        raise NeedToSwitchException

    sato = False
    if bot.self_id in config.allowed_accounts:
        sato = rng.choice([True, False], p=[0.1, 0.9])

    imgpath = "./Static/Cum/0.png"
    if sato:
        imgpath = "./Static/Cum/1.png"
    msg = MessageSegment.image(Path(imgpath))
    await cum.send(msg)


@eatbreak.handle()
async def _(event: GroupMessageEvent):
    msg = (
        MessageSegment.text("谢谢mai~"),
        MessageSegment.image(Path("./Static/EatBreak/0.png")),
    )
    await eatbreak.send(msg, at_sender=True)
