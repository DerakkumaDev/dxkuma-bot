import os

import aiofiles
from nonebot import on_fullmatch

from util.permission import ADMIN

block = on_fullmatch("禁st", ignorecase=True, permission=ADMIN)
unlock = on_fullmatch("解st", ignorecase=True, permission=ADMIN)


@block.handle()
async def _():
    async with aiofiles.open("./data/nsfw_lock", "w"):
        pass

    await block.send("已禁用")


@unlock.handle()
async def _():
    if os.path.exists("./data/nsfw_lock"):
        os.remove("./data/nsfw_lock")

    await unlock.send("已恢复")
