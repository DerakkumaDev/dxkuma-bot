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
    qq = event.get_user_id()
    if qq == bot.self_id:
        return
    group_id = event.group_id
    user_name = (await bot.get_stranger_info(user_id=int(qq)))["nickname"]
    if group_id == config.special_group:
        msg = MessageSegment.text(
            f"恭喜{user_name}（{qq}）发现了迪拉熊宝藏地带，发送dlxhelp试一下吧~"
        )
    else:
        msg = MessageSegment.text(
            f"欢迎{user_name}（{qq}）加入本群，发送dlxhelp和迪拉熊一起玩吧~"
        )
    await groupIncrease.send(
        (msg, MessageSegment.image(Path("./Static/MemberChange/0.png")))
    )


@groupDecrease.handle()
async def _(bot: Bot, event: GroupDecreaseNoticeEvent):
    qq = event.get_user_id()
    group_id = event.group_id
    user_name = (await bot.get_stranger_info(user_id=int(qq)))["nickname"]
    if group_id == config.special_group:
        msg = MessageSegment.text(f"很遗憾，{user_name}（{qq}）离开了迪拉熊的小窝QAQ")
    else:
        msg = MessageSegment.text(f"{user_name}（{qq}）离开了迪拉熊QAQ")
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
    await event.approve(bot)


@groupRequest.handle()
async def _(bot: Bot, event: GroupRequestEvent):
    if bot.self_id in config.allowed_accounts:  # 支持nsfw内容的账号需要审核
        return
    if event.sub_type != "invite":
        return
    await event.approve(bot)
    qq = event.get_user_id()
    group_id = event.group_id
    user_name = (await bot.get_stranger_info(user_id=int(qq)))["nickname"]
    msg = MessageSegment.text(
        f"迪拉熊由{user_name}（{qq}）邀请加入了本群，发送dlxhelp和迪拉熊一起玩吧~"
    )
    await bot.send_msg(
        group_id=group_id,
        message=(msg, MessageSegment.image(Path("./Static/MemberChange/0.png"))),
    )
