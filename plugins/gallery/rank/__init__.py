import os
import re

from nonebot import on_regex
from nonebot.adapters.onebot.v11 import Bot

from ..random_bvid.database import bvidList
from ..rank.database import ranking

rank = on_regex(r"^(迪拉熊|dlx)(排行榜|rank)$", re.I)


@rank.handle()
async def _(bot: Bot):
    time = ranking.now

    leaderboard = ranking.gen_rank(time)

    leaderboard_output = list()
    count = min(len(leaderboard), 5)  # 最多显示5个人，取实际人数和5的较小值
    for i, (qq, total_count) in enumerate(leaderboard[:count], start=1):
        user_name = (await bot.get_stranger_info(user_id=qq))["nickname"]
        rank_str = f"{i}. {user_name}：{total_count}"
        leaderboard_output.append(rank_str)

    msg = "\r\n".join(leaderboard_output)
    msg = f"本周迪拉熊厨力最高的人是……\r\n{msg}\r\n迪拉熊给上面{count}个宝宝一个大大的拥抱~\r\n（积分每周重算）\r\n\r\n图库：{len(os.listdir(ranking.pic_path))}:{len(os.listdir(ranking.nsfw_pic_path))}\r\n视频库：{bvidList.count}"
    await rank.finish(msg)
