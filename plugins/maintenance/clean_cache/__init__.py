from nonebot import on_fullmatch
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent

from util.Config import config
from util.exceptions import NotAllowedException

clean_cache = on_fullmatch("清缓存")


@clean_cache.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    if event.user_id not in config.admin_accounts:
        return

    await clean_cache.send("开始清空缓存")
    await bot.call_api("clean_cache")
    await clean_cache.send("缓存清空完成")
    raise NotAllowedException
