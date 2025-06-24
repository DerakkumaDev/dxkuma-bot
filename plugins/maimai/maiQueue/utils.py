import time

from nonebot.adapters.onebot.v11 import Bot

from .database import arcadeManager


async def gen_message(bot: Bot, arcade_id: str) -> str:
    arcade = arcadeManager.get_arcade(arcade_id)
    messages = list()
    messages.append(arcade["name"])
    messages.append(f"实时人数：{arcade["count"]}人")
    if arcade["last_action"] is not None:
        if (
            arcade["last_action"]["group"] == -1
            and arcade["last_action"]["operator"] == -1
        ):
            messages.append(f"最后操作者：迪拉熊")
        else:
            operator = await bot.get_stranger_info(
                user_id=arcade["last_action"]["operator"]
            )
            messages.append(
                f"最后操作者：{arcade["last_action"]["group"]} - {operator["nickname"]}（{operator["qid"] or arcade["last_action"]["operator"]}）"
            )
        messages.append(
            f"\t于{time.strftime("%Y年%m月%d日 %H:%M", time.localtime(arcade["last_action"]["time"]))}（UTC+8）由{arcade["last_action"]["action"]["before"]}人{action2str(arcade["last_action"]["action"]["type"])}{arcade["last_action"]["action"]["num"]}人"
        )
    messages.append(f"今日（UTC+4）被操作次数：{arcade["action_times"]}")
    return "\r\n".join(messages)


def action2str(action: str) -> str:
    match action:
        case "add":
            return "增加"
        case "remove":
            return "减少"
        case "set":
            return "设置"
