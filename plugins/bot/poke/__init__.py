from pathlib import Path
from random import SystemRandom

from nonebot import on_type
from nonebot.adapters.onebot.v11 import Bot, MessageSegment, PokeNotifyEvent
from nonebot.rule import to_me

random = SystemRandom()

poke = on_type(PokeNotifyEvent, rule=to_me())

POKE_PIC = Path("./Static/Poke/")

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
async def _(bot: Bot, event: PokeNotifyEvent):
    qq = event.get_user_id()
    if not event.group_id or qq == bot.self_id:
        return
    weights = [9, 9, 9, 9, 9, 9, 9, 9, 4, 4]
    ran_number = random.choices(range(1, 11), weights=weights, k=1)[0]
    text = conversations[ran_number]
    filename = f"{ran_number - 1}.png"
    file_path = POKE_PIC / filename
    msg = (MessageSegment.text(text), MessageSegment.image(file_path))
    await poke.finish(msg)
