from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message
from nonebot.internal.rule import Rule
from nonebot.typing import T_State
from xxhash import xxh32_hexdigest

from . import config

repeater_group = config.repeater_group
shortest = config.shortest_length
blacklist = config.blacklist


# 消息预处理
def message_preprocess(message: Message) -> str:
    return str().join(
        seg.to_rich_text(truncate=None) if seg.type != "image" else seg.data["file"]
        for seg in message
    )


class RepeaterRule:
    __slots__ = ()

    def __repr__(self) -> str:
        return "RepeaterRule()"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, RepeaterRule)

    def __hash__(self) -> int:
        return hash((self.__class__,))

    async def __call__(self, event: GroupMessageEvent, state: T_State) -> bool:
        # 检查是否在黑名单中
        if event.raw_message in blacklist:
            return False

        gid = str(event.group_id)
        if gid not in repeater_group and "all" not in repeater_group:
            return False

        message_str = message_preprocess(event.get_message())
        digest = xxh32_hexdigest(message_str)
        if config.last_message.get(gid, str()) != digest:
            config.last_message[gid] = digest
            config.message_times[gid] = list()

        qq = event.user_id
        if qq in config.message_times[gid]:
            return False

        config.message_times[gid].append(qq)
        if len(config.message_times[gid]) != config.shortest_times:
            return False

        return True


def repeater() -> Rule:
    return Rule(RepeaterRule())
