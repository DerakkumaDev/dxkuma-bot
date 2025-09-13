from datetime import timedelta, timezone
import re

from nonebot import on_regex
from nonebot.adapters.onebot.v11 import GroupMessageEvent
from numpy import random

from util.stars import stars

query = on_regex(r"^查星星$", re.I)
query_detail = on_regex(r"^查?星星明细$", re.I)

replies_posi: list = [
    lambda _: "可以给迪拉熊吃一颗吗mai？（可怜）",
    lambda stars: f"迪拉熊帮你把★放在下面啦~\r\n{'★' * stars}"
    if stars < 66
    else "好多★呀，迪拉熊要数不过来了mai~（晕）",
]

replies_nega: list = [
    lambda _: "你欠迪拉熊的什么时候还mai！（怒）",
]


@query.handle()
async def _(event: GroupMessageEvent):
    rng = random.default_rng()
    qq = event.get_user_id()
    balance = await stars.get_balance(qq)
    if balance == "inf":
        await query.finish("你现在有∞颗★哦~", at_sender=True)
    elif balance > 0:
        reply = rng.choice(replies_posi)
        await query.finish(
            f"你现在有{balance}颗★哦~{reply(balance)}\r\n"
            "使用图库功能时迪拉熊会奖励星星哦~",
            at_sender=True,
        )
    elif balance < 0:
        reply = rng.choice(replies_nega)
        await query.finish(
            f"你还欠迪拉熊{balance}颗★mai！{reply(balance)}\r\n"
            "使用图库功能时迪拉熊会奖励星星哦~",
            at_sender=True,
        )

    await query.send(
        "你还没有★mai~\r\n使用图库功能时迪拉熊会奖励星星哦~", at_sender=True
    )


@query_detail.handle()
async def _(event: GroupMessageEvent):
    qq = event.get_user_id()
    details = await stars.list_actions(qq, 10)
    details_text = "\r\n".join(
        f"{
            detail['created_at']
            .astimezone(timezone(timedelta(hours=8)))
            .strftime('%-y/%-m/%-d %-H:%M%z')
        } {detail['change']}★ {detail['cause']}"
        for detail in details
    )
    await query.send(
        f"你最近{len(details)}次的明细是——\r\n{details_text}", at_sender=True
    )
