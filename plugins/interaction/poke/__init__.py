from pathlib import Path

from nonebot import on_type
from nonebot.adapters.onebot.v11 import MessageSegment, PokeNotifyEvent
from nonebot.rule import to_me
from numpy import random

poke = on_type(PokeNotifyEvent, to_me())

conversations = {
    1: "不可以戳迪拉熊的屁股啦~",
    2: "你怎么可以戳迪拉熊的屁股！",
    3: "为什么要戳迪拉熊的屁股呢？",
    4: "再戳迪拉熊的屁股就不跟你玩了！",
    5: "你再戳一下试试！",
    6: "讨厌啦~不要戳迪拉熊的屁股啦~",
    7: "你觉得戳迪拉熊的屁股很好玩吗？",
    8: "不要再戳迪拉熊的屁股啦！",
    9: "迪拉熊懂你的意思~",
    10: "再戳迪拉熊就跟你绝交！",
}


@poke.handle()
async def _(event: PokeNotifyEvent):
    rng = random.default_rng()
    if not event.group_id:
        return
    weights = [
        0.1125,
        0.1125,
        0.1125,
        0.1125,
        0.1125,
        0.1125,
        0.1125,
        0.1125,
        0.05,
        0.05,
    ]
    ran_number = rng.choice(range(1, 11), p=weights)
    text = conversations[ran_number]
    filename = f"{ran_number - 1}.png"
    file_path = Path("./Static/Poke/") / filename
    msg = (MessageSegment.text(text), MessageSegment.image(file_path))
    await poke.finish(msg)
