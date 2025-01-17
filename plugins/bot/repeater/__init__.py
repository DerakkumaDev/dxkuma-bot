from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message

from . import config

repeater_group = config.repeater_group
shortest = config.shortest_length
blacklist = config.blacklist

m = on_message(priority=10, block=False)

last_message = dict()
message_times = dict()


# 消息预处理
def message_preprocess(message: Message):
    message_str = str(message)
    contained_images = list()
    for i in message:
        if i.type != "image":
            continue

        file = i.data["file"]
        contained_images.append((str(i), file))

    for i, v in contained_images:
        message_str = message_str.replace(i, v)

    return message_str, message


@m.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    # 检查是否在黑名单中
    if event.raw_message in blacklist:
        return

    gid = str(event.group_id)
    if gid in repeater_group or "all" in repeater_group:
        message_str, message = message_preprocess(event.get_message())
        qq = event.get_user_id()
        if last_message.get(gid) != message_str:
            message_times[gid] = set()

        message_times[gid].add(hash(qq))
        if len(message_times.get(gid)) == config.shortest_times:
            await bot.send_group_msg(group_id=event.group_id, message=message)

        last_message[gid] = message_str
