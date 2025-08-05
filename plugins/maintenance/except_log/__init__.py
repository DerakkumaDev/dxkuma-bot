import traceback
from typing import Optional

from aiohttp import ClientError
from nonebot import get_bot
from nonebot.adapters.onebot.v11 import MessageSegment, Event, MessageEvent
from nonebot.adapters.onebot.v11.exception import OneBotV11AdapterException
from nonebot.internal.matcher import Matcher
from nonebot.message import run_postprocessor
from starlette.websockets import WebSocketDisconnect

from util.Config import config
from util.exceptions import NotAllowedException, NeedToSwitchException

PICPATH = "./Static/Gallery/SFW/"


@run_postprocessor
async def _(event: Event, matcher: Matcher, exception: Optional[Exception]):
    if not exception or isinstance(
        exception,
        (
            OneBotV11AdapterException,
            WebSocketDisconnect,
            ClientError,
            NotAllowedException,
            NeedToSwitchException,
        ),
    ):
        return
    bot = get_bot()
    trace = str().join(traceback.format_exception(exception)).replace("\\n", "\r\n")
    msg = MessageSegment.text(
        f"{trace}{
            event.get_message().to_rich_text()
            if isinstance(event, MessageEvent)
            else event.get_type()
        }"
    )
    await bot.send_msg(group_id=config.dev_group, message=msg)
