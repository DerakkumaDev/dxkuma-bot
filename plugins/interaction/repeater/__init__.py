from nonebot import on_message
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message
from xxhash import xxh32_hexdigest

from . import config

repeater_group = config.repeater_group
shortest = config.shortest_length
blacklist = config.blacklist

m = on_message(priority=1000)

last_message = dict()
message_times = dict()


# 消息预处理
def message_preprocess(message: Message):
    return (
        "".join(
            seg.to_rich_text(truncate=None) if seg.type != "image" else seg.data["file"]
            for seg in message
        ),
        message,
    )


@m.handle()
async def _(event: GroupMessageEvent):
    # 检查是否在黑名单中
    if event.raw_message in blacklist:
        return

    gid = str(event.group_id)
    if gid in repeater_group or "all" in repeater_group:
        message_str, message = message_preprocess(event.get_message())
        qq = event.user_id
        if last_message.get(gid) != message_str:
            message_times[gid] = set()

        message_times[gid].add(qq)
        if len(message_times.get(gid)) == config.shortest_times:
            await m.send(message)

        last_message[gid] = xxh32_hexdigest(message_str)
