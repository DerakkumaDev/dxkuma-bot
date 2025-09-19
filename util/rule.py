import re

from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import GroupMessageEvent
from nonebot.consts import REGEX_MATCHED
from nonebot.internal.rule import Rule
from nonebot.params import EventToMe
from nonebot.typing import T_State

from util.config import config


class RegexRule:
    """检查消息字符串是否符合指定正则表达式。

    参数:
        regex: 正则表达式
        flags: 正则表达式标记
    """

    __slots__ = ("flags", "regex")

    def __init__(self, regex: str, flags: int = 0):
        self.regex = regex
        self.flags = flags

    def __repr__(self) -> str:
        return f"Regex(regex={self.regex!r}, flags={self.flags})"

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, RegexRule)
            and self.regex == other.regex
            and self.flags == other.flags
        )

    def __hash__(self) -> int:
        return hash((self.regex, self.flags))

    async def __call__(self, event: Event, state: T_State) -> bool:
        try:
            text = event.get_plaintext()
        except Exception:
            return False
        if event.at_me or event.reply:
            return False
        if matched := re.search(self.regex, text.strip(), self.flags):
            state[REGEX_MATCHED] = matched
            return True
        else:
            return False


class AtMeRule:
    """检查事件是否与机器人有关。"""

    __slots__ = ()

    def __repr__(self) -> str:
        return "AtMe()"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, AtMeRule)

    def __hash__(self) -> int:
        return hash((self.__class__,))

    async def __call__(self, event: Event, to_me: bool = EventToMe()) -> bool:
        return to_me and (
            not isinstance(event, GroupMessageEvent)
            or not event.reply
            or str(event.reply.sender.user_id) not in config.bots
        )


def at_me() -> Rule:
    """匹配与机器人有关的事件。"""

    return Rule(AtMeRule())
