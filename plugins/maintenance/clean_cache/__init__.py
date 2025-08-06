from nonebot import on_fullmatch
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent

from util.exceptions import NotAllowedException
from util.permission import ADMIN

clean_cache = on_fullmatch("清缓存", permission=ADMIN)


@clean_cache.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    await clean_cache.send("开始清空缓存")
    await bot.clean_cache()
    await clean_cache.send("缓存清空完成")
    raise NotAllowedException
