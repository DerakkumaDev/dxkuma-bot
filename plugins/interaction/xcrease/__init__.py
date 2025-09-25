from pathlib import Path

from nonebot import on_type
from nonebot.adapters.onebot.v11 import (
    Bot,
    FriendAddNoticeEvent,
    FriendRequestEvent,
    GroupDecreaseNoticeEvent,
    GroupIncreaseNoticeEvent,
    GroupRequestEvent,
    MessageSegment,
)

from util.config import config

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
        msg = f"恭喜{user_info['nickname']}（{
            user_info['qid'] or qq
        }）发现了迪拉熊宝藏地带，发送“dlxhelp”试一下吧~"
    else:
        msg = f"欢迎{user_info['nickname']}（{
            user_info['qid'] or qq
        }）加入本群，发送“dlxhelp”和迪拉熊一起玩吧~"
    await groupIncrease.send(
        (
            MessageSegment.text(msg),
            MessageSegment.image(Path("./Static/MemberChange/0.png")),
        )
    )


@groupDecrease.handle()
async def _(bot: Bot, event: GroupDecreaseNoticeEvent):
    if event.is_tome():
        return
    qq = event.user_id
    group_id = event.group_id
    user_info = await bot.get_stranger_info(user_id=qq)
    if group_id == config.special_group:
        msg = f"很遗憾，{user_info['nickname']}（{
            user_info['qid'] or qq
        }）离开了迪拉熊的小窝TAT"
    else:
        msg = f"{user_info['nickname']}（{user_info['qid'] or qq}）离开了迪拉熊TAT"

    await groupDecrease.send(
        (
            MessageSegment.text(msg),
            MessageSegment.image(Path("./Static/MemberChange/1.png")),
        )
    )


@friendAdd.handle()
async def _():
    msg = (
        MessageSegment.text("恭喜你发现了迪拉熊宝藏地带，发送“dlxhelp”试一下吧~"),
        MessageSegment.image(Path("./Static/MemberChange/0.png")),
    )
    await friendAdd.send(msg)


@friendRequest.handle()
async def _(bot: Bot, event: FriendRequestEvent):
    if event.self_id not in config.auto_agree:
        return
    await event.approve(bot)


@groupRequest.handle()
async def _(bot: Bot, event: GroupRequestEvent):
    if event.sub_type != "invite":
        return
    if event.self_id not in config.auto_agree:
        return
    await event.approve(bot)
    qq = event.user_id
    group_id = event.group_id
    user_info = await bot.get_stranger_info(user_id=qq)
    msg = (
        MessageSegment.text(
            f"迪拉熊由{user_info['nickname']}（{
                qq
            }）邀请加入了本群，发送“dlxhelp”和迪拉熊一起玩吧~"
        ),
        MessageSegment.image(Path("./Static/MemberChange/0.png")),
    )
    await bot.send_msg(group_id=group_id, message=msg)
