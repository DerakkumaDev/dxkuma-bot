import traceback
from typing import Optional

from httpx import HTTPError
from nonebot import get_bot
from nonebot.adapters.onebot.v11 import Event, MessageEvent, MessageSegment
from nonebot.exception import AdapterException, IgnoredException
from nonebot.message import run_postprocessor
from starlette.websockets import WebSocketDisconnect

from util.config import config
from util.exceptions import ContinuedException

PICPATH = "./Static/Gallery/SFW/"


@run_postprocessor
async def _(event: Event, exception: Optional[Exception]):
    if not exception or isinstance(
        exception,
        (
            HTTPError,
            AdapterException,
            IgnoredException,
            ContinuedException,
            WebSocketDisconnect,
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
