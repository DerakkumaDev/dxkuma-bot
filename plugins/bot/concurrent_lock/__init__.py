from nonebot.adapters.onebot.v11 import (
    GroupMessageEvent,
    GroupIncreaseNoticeEvent,
    GroupDecreaseNoticeEvent,
)
from nonebot.exception import IgnoredException
from nonebot.message import event_preprocessor, run_postprocessor, event_postprocessor

from util.exceptions import NotAllowedException, NeedToSwitchException, SkipException
from .util import locks, Lock, States


@event_preprocessor
async def _(
    event: GroupMessageEvent | GroupIncreaseNoticeEvent | GroupDecreaseNoticeEvent,
):
    if event.is_tome():
        return

    key = hash(f"{event.group_id}{event.user_id}{event.time}")
    if key not in locks:
        locks[key] = Lock()

    locks[key].count += 1
    await locks[key].semaphore.acquire()
    if locks[key].state == States.PROCESSED:
        if locks[key].count > 1:
            locks[key].count -= 1
            locks[key].semaphore.release()
        else:
            del locks[key]

        raise IgnoredException(SkipException)

    return


@run_postprocessor
async def _(
    event: GroupMessageEvent | GroupIncreaseNoticeEvent | GroupDecreaseNoticeEvent,
    exception: Exception | None,
):
    if event.is_tome():
        return

    key = hash(f"{event.group_id}{event.user_id}{event.time}")
    if isinstance(exception, NotAllowedException):
        locks[key].state = States.SKIPED
        return

    if isinstance(exception, NeedToSwitchException):
        locks[key].state = States.NEED_TO_SWITCH
        return

    locks[key].state = States.PROCESSED


@event_postprocessor
async def _(
    event: GroupMessageEvent | GroupIncreaseNoticeEvent | GroupDecreaseNoticeEvent,
):
    if event.is_tome():
        return

    key = hash(f"{event.group_id}{event.user_id}{event.time}")
    locks[key].count -= 1
    if locks[key].state == States.PROCESSED:
        if locks[key].count <= 0:
            del locks[key]
            return

    locks[key].semaphore.release()
