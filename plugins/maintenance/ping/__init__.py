from nonebot import on_fullmatch
from nonebot.adapters.onebot.v11 import GroupMessageEvent

from util.Config import config
from util.exceptions import NotAllowedException

ping = on_fullmatch("ping", ignorecase=True)


@ping.handle()
async def _(event: GroupMessageEvent):
    if event.user_id not in config.admin_accounts:
        return

    msg = event.get_plaintext()
    msg = msg.replace("i", "o")
    msg = msg.replace("I", "O")
    await ping.send(msg)
    raise NotAllowedException
