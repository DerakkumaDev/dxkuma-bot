import re
from argparse import Namespace as Namespace
from typing import Union

from nonebot.adapters import Event
from nonebot.consts import REGEX_MATCHED
from nonebot.internal.rule import Rule as Rule
from nonebot.typing import T_State


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
            text = event.get_message().extract_plain_text().strip()
        except Exception:
            return False
        if matched := re.search(self.regex, text, self.flags):
            state[REGEX_MATCHED] = matched
            return True
        else:
            return False


def regex(regex: str, flags: Union[int, re.RegexFlag] = 0) -> Rule:
    return Rule(RegexRule(regex, flags))
