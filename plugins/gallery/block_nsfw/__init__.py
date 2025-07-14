import os

import aiofiles
from nonebot import on_fullmatch
from nonebot.adapters.onebot.v11 import MessageEvent

from util.Config import config

block = on_fullmatch("禁st", ignorecase=True)
unlock = on_fullmatch("解st", ignorecase=True)


@block.handle()
async def _(event: MessageEvent):
    if event.user_id not in config.admin_accounts:
        return

    async with aiofiles.open("./data/nsfw_lock", "w"):
        pass

    await block.send("st功能已禁用")


@unlock.handle()
async def _(event: MessageEvent):
    if event.user_id not in config.admin_accounts:
        return

    if os.path.exists("./data/nsfw_lock"):
        os.remove("./data/nsfw_lock")

    await unlock.send("st功能已恢复")
