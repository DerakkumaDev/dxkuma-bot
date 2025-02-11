from nonebot import on_fullmatch
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent

from util.Config import config
from util.exceptions import NotAllowedException

ping = on_fullmatch("ping", ignorecase=True)


@ping.handle()
async def _(bot: Bot, event):
    if isinstance(event, GroupMessageEvent) and event.group_id != config.dev_group:
        return

    await ping.send("PONG")
    raise NotAllowedException
