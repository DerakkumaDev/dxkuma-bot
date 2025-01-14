import re
from pathlib import Path

from nonebot import on_regex
from nonebot.adapters.onebot.v11 import Bot, MessageSegment, GroupMessageEvent

from util.Config import config
from util.exceptions import NeedToSwitchException
from ..handle_lock.util import locks

all_help = on_regex(r"^((迪拉熊|dlx)(help|指令|帮助)|指令大全)$", re.I)


@all_help.handle()
async def _(bot: Bot, event):
    if isinstance(event, GroupMessageEvent):
        key = f"{event.group_id}{event.user_id}{event.time}".__hash__()
        if (
            key in locks
            and locks[key].count > 0
            and bot.self_id not in config.allowed_accounts
        ):
            raise NeedToSwitchException

    path = (
        "./Static/Help/1.png"
        if bot.self_id in config.allowed_accounts
        else "./Static/Help/0.png"
    )
    msg = (
        MessageSegment.image(Path(path)),
        MessageSegment.text("迪拉熊测试群：959231211"),
    )
    await all_help.send(msg)
