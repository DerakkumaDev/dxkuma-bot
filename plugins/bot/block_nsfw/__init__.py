import os
import re

from nonebot import on_regex
from nonebot.adapters.onebot.v11 import MessageEvent

from util.Config import config

block = on_regex(r"^禁st$", re.I)
unlock = on_regex(r"^解st$", re.I)


@block.handle()
async def _(event: MessageEvent):
    if event.user_id not in config.admin_accounts:
        return

    with open("./data/nsfw_lock", "w"):
        pass

    await block.send("st功能已禁用")


@unlock.handle()
async def _(event: MessageEvent):
    if event.user_id not in config.admin_accounts:
        return

    if os.path.exists("./data/nsfw_lock"):
        os.remove("./data/nsfw_lock")

    await unlock.send("st功能已恢复")
