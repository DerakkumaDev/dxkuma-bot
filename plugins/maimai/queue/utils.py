from datetime import timedelta, timezone
from nonebot.adapters.onebot.v11 import Bot


async def gen_message(bot: Bot, arcade: dict) -> str:
    if arcade["last_action"] is None:
        return "从未更新过"

    messages = list()
    if arcade["count"] > 0:
        messages.append(f"当前为{arcade['count']}卡")
    else:
        messages.append("当前无人排卡")

    messages.append(
        f"最后在{
            arcade['last_action']['time']
            .astimezone(timezone(timedelta(hours=8)))
            .strftime('%-y年%-m月%-d日 %-H:%-M%z')
        }"
    )
    action, delta = num2action(arcade["count"], arcade["last_action"]["before"])
    if arcade["last_action"]["group"] < 0 and arcade["last_action"]["operator"] < 0:
        messages.append(f"由迪拉熊{action}{delta}卡")
    else:
        group_info = dict()
        operator = dict()
        try:
            group_info = await bot.get_group_info(
                group_id=arcade["last_action"]["group"]
            )
        except Exception:
            pass
        try:
            operator = await bot.get_group_member_info(
                group_id=arcade["last_action"]["group"],
                user_id=arcade["last_action"]["operator"],
            )
        except Exception:
            try:
                operator = await bot.get_stranger_info(
                    user_id=arcade["last_action"]["operator"]
                )
            except Exception:
                pass
        messages.append(
            f"由{group_info.get('group_name', arcade['last_action']['group'])}::{
                operator.get('card', str())
                or operator.get('nickname', arcade['last_action']['operator'])
            }{action}{delta}卡"
        )
    if arcade["action_times"] > 0:
        messages.append(f"为今日（UTC+4）第{arcade['action_times']}次更新")
    else:
        messages.append("今日（UTC+4）还没有被更新过")

    return "\r\n".join(messages)


def num2action(now: int, before: int) -> tuple[str, int]:
    if now > before:
        return "增加", now - before
    elif now < before:
        return "减少", before - now

    return "减少", 0
