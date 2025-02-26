from nonebot import on_fullmatch, get_bot
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.internal.driver import Driver

from util.Config import config
from util.exceptions import NotAllowedException

ping = on_fullmatch("ping", ignorecase=True)


@ping.handle()
async def _(event: GroupMessageEvent):
    if event.group_id != config.dev_group:
        return

    await ping.send("PONG")
    raise NotAllowedException


@Driver.on_bot_disconnect
async def _(bot: Bot):
    sender = get_bot()
    await sender.send_group_msg(
        group_id=config.dev_group, message=f"{bot.self_id} is DOWN"
    )
