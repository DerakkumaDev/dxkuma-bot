import re

from nonebot.adapters.onebot.v11 import GroupMessageEvent
from nonebot.internal.rule import Rule
from nonebot.typing import T_State

from util.config import config


class NSFWRule:
    __slots__ = ()

    def __repr__(self) -> str:
        return "RepeaterRule()"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, NSFWRule)

    def __hash__(self) -> int:
        return hash((self.__class__,))

    async def __call__(self, event: GroupMessageEvent, state: T_State) -> bool:
        if not re.search(r"(涩|色|瑟)图|st", event.get_plaintext(), re.I):
            # type 不为 'nsfw'
            return True

        if event.self_id in config.nsfw_allowed:
            # type 为 'nsfw' 且为指定机器人
            return True

        return False


def nsfw() -> Rule:
    return Rule(NSFWRule())
