from pathlib import Path

from nonebot import on_type
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupIncreaseNoticeEvent,
    GroupDecreaseNoticeEvent,
    FriendAddNoticeEvent,
    FriendRequestEvent,
    GroupRequestEvent,
    MessageSegment,
)

from util.Config import config

groupIncrease = on_type(GroupIncreaseNoticeEvent)
groupDecrease = on_type(GroupDecreaseNoticeEvent)
friendAdd = on_type(FriendAddNoticeEvent)
friendRequest = on_type(FriendRequestEvent)
groupRequest = on_type(GroupRequestEvent)


@groupIncrease.handle()
async def _(bot: Bot, event: GroupIncreaseNoticeEvent):
    if event.is_tome():
        return
    qq = event.user_id
    group_id = event.group_id
    user_info = await bot.get_stranger_info(user_id=qq)
    if group_id == config.special_group:
        msg = MessageSegment.text(
            f"恭喜{user_info['nickname']}（{user_info['qid'] or qq}）发现了迪拉熊宝藏地带，发送dlxhelp试一下吧~"
        )
    else:
        msg = MessageSegment.text(
            f"欢迎{user_info['nickname']}（{user_info['qid'] or qq}）加入本群，发送dlxhelp和迪拉熊一起玩吧~"
        )
    await groupIncrease.send(
        (msg, MessageSegment.image(Path("./Static/MemberChange/0.png")))
    )


@groupDecrease.handle()
async def _(bot: Bot, event: GroupDecreaseNoticeEvent):
    if event.is_tome():
        return
    qq = event.user_id
    group_id = event.group_id
    user_info = await bot.get_stranger_info(user_id=qq)
    if group_id == config.special_group:
        msg = MessageSegment.text(
            f"很遗憾，{user_info['nickname']}（{user_info['qid'] or qq}）离开了迪拉熊的小窝TAT"
        )
    else:
        msg = MessageSegment.text(
            f"{user_info['nickname']}（{user_info['qid'] or qq}）离开了迪拉熊TAT"
        )
    await groupDecrease.send(
        (msg, MessageSegment.image(Path("./Static/MemberChange/1.png")))
    )


@friendAdd.handle()
async def _():
    msg = MessageSegment.text("恭喜你发现了迪拉熊宝藏地带，发送dlxhelp试一下吧~")
    await friendAdd.send(
        (msg, MessageSegment.image(Path("./Static/MemberChange/0.png")))
    )


@friendRequest.handle()
async def _(bot: Bot, event: FriendRequestEvent):
    if event.self_id in config.auto_agree:
        return
    await event.approve(bot)


@groupRequest.handle()
async def _(bot: Bot, event: GroupRequestEvent):
    if event.sub_type != "invite":
        return
    if event.self_id in config.auto_agree:
        return
    await event.approve(bot)
    qq = event.user_id
    group_id = event.group_id
    user_info = await bot.get_stranger_info(user_id=qq)
    msg = MessageSegment.text(
        f"迪拉熊由{user_info['nickname']}（{qq}）邀请加入了本群，发送dlxhelp和迪拉熊一起玩吧~"
    )
    await bot.send_msg(
        group_id=group_id,
        message=(msg, MessageSegment.image(Path("./Static/MemberChange/0.png"))),
    )
