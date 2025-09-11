import re
from pathlib import Path

from nonebot import on_fullmatch, on_regex
from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageSegment
from nonebot.rule import to_me
from numpy import random
from xxhash import xxh32_hexdigest

from util.config import config
from util.exceptions import SkipedException
from util.lock import locks

xc = on_regex(r"^([香想]草|xc)(迪拉熊|dlx)$", re.I)
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
    9: "不把白系AP了就别想！",
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
        return
    if len(set(roll_list)) == 1:
        msg = (
            MessageSegment.text("就一个选项要迪拉熊怎么选mai~"),
            MessageSegment.image(Path("./Static/Roll/1.png")),
        )
        await roll.finish(msg, at_sender=True)
    output = rng.choice(roll_list)
    msg = (
        MessageSegment.text(f"迪拉熊建议你选择“{output}”mai~"),
        MessageSegment.image(Path("./Static/Roll/0.png")),
    )
    await roll.send(msg, at_sender=True)


@cum.handle()
async def _(event: GroupMessageEvent):
    rng = random.default_rng()
    i = 0
    key = xxh32_hexdigest(f"{event.time}_{event.group_id}_{event.real_seq}")
    if event.self_id not in config.nsfw_allowed:
        if key in locks and locks[key].count > 1:
            raise SkipedException
    else:
        i = rng.choice([0, 1], p=[0.1, 0.9])

    msg = MessageSegment.image(Path(f"./Static/Cum/{i}.png"))
    await cum.send(msg)


@eatbreak.handle()
async def _(event: GroupMessageEvent):
    msg = (
        MessageSegment.text("谢谢mai~"),
        MessageSegment.image(Path("./Static/EatBreak/0.png")),
    )
    await eatbreak.send(msg, at_sender=True)
