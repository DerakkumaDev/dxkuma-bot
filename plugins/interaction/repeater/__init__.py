from nonebot import on_message
from nonebot.adapters.onebot.v11 import GroupMessageEvent

from .rule import repeater

m = on_message(repeater())


@m.handle()
async def _(event: GroupMessageEvent):
    await m.send(event.get_message())
