from nonebot import on_fullmatch
from nonebot.adapters.onebot.v11 import GroupMessageEvent

from util.exceptions import NotAllowedException
from util.permission import ADMIN

ping = on_fullmatch("ping", ignorecase=True, permission=ADMIN)


@ping.handle()
async def _(event: GroupMessageEvent):
    msg = event.get_plaintext()
    msg = msg.replace("i", "o")
    msg = msg.replace("I", "O")
    await ping.send(msg)
    raise NotAllowedException
