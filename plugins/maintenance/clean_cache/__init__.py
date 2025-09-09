from nonebot import on_fullmatch
from nonebot.adapters.onebot.v11 import Bot

from util.exceptions import ContinuedException
from util.permission import ADMIN

clean_cache = on_fullmatch("清缓存", permission=ADMIN)


@clean_cache.handle()
async def _(bot: Bot):
    await clean_cache.send("开始")
    await bot.clean_cache()
    await clean_cache.send("完成")
    raise ContinuedException
