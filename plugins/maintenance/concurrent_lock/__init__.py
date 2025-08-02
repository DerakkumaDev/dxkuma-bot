from nonebot.adapters.onebot.v11 import (
    Bot,
    Event,
    GroupMessageEvent,
    GroupIncreaseNoticeEvent,
    GroupDecreaseNoticeEvent,
)
from nonebot.exception import IgnoredException
from nonebot.internal.driver import Driver
from nonebot.message import event_preprocessor, run_postprocessor, event_postprocessor
from xxhash import xxh32_hexdigest

from util.Config import config
from util.exceptions import NotAllowedException, NeedToSwitchException, SkipException
from util.lock import locks, Lock, States


@event_preprocessor
async def _(
    bot: Bot,
    event: GroupMessageEvent | GroupIncreaseNoticeEvent | GroupDecreaseNoticeEvent,
):
    if event.get_user_id() in config.bots:
        raise IgnoredException(SkipException)

    check_event(event)

    key = xxh32_hexdigest(
        f"{event.time}_{event.group_id}_{event.real_seq if isinstance(event, GroupMessageEvent) else event.user_id}"
    )
    if key not in locks:
        locks[key] = Lock()

    await locks[key].semaphore.acquire()
    if locks[key].state == States.PROCESSED:
        if locks[key].count > 1:
            locks[key].bots.append(bot.self_id)
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
    key = xxh32_hexdigest(
        f"{event.time}_{event.group_id}_{event.real_seq if isinstance(event, GroupMessageEvent) else event.user_id}"
    )
    if isinstance(exception, NotAllowedException):
        locks[key].state = States.SKIPED
        return

    if isinstance(exception, NeedToSwitchException):
        locks[key].state = States.NEED_TO_SWITCH
        return

    locks[key].state = States.PROCESSED


@event_postprocessor
async def _(
    bot: Bot,
    event: GroupMessageEvent | GroupIncreaseNoticeEvent | GroupDecreaseNoticeEvent,
):
    key = xxh32_hexdigest(
        f"{event.time}_{event.group_id}_{event.real_seq if isinstance(event, GroupMessageEvent) else event.user_id}"
    )
    locks[key].bots.append(bot.self_id)
    if locks[key].state == States.PROCESSED:
        if locks[key].count <= 0:
            del locks[key]
            return

    locks[key].semaphore.release()


@Driver.on_bot_connect
async def _(bot: Bot):
    config.bots.append(bot.self_id)


@Driver.on_bot_disconnect
async def _(bot: Bot):
    config.bots.remove(bot.self_id)


def check_event(event: Event):
    if isinstance(event, GroupMessageEvent) and "at" in (
        message := event.get_message()
    ):
        if ats := message["at"]:
            for at in ats:
                if at.data["qq"] in config.bots and not event.is_tome():
                    raise IgnoredException(SkipException)
