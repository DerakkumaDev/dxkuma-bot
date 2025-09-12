from nonebot import on_regex
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment

from util.stars import stars
from util.permission import ADMIN

infstars = on_regex(r"^\s*无限星星\s*$", permission=ADMIN)


@infstars.handle()
async def _(event: MessageEvent):
    for seg in event.get_message()["at"]:
        qq = seg.data["qq"]
        await stars.set_inf_balance(qq, True)
        await infstars.send((MessageSegment.at(qq), MessageSegment.text(" 成功")))
