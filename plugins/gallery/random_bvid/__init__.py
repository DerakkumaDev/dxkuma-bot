import re
from datetime import datetime, timedelta, timezone

import orjson as json
from httpx import AsyncClient, URL
from nonebot import on_regex
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    MessageEvent,
    MessageSegment,
)

from util.config import config
from util.permission import ADMIN
from util.stars import stars
from .database import bvidList
from ..rank.database import ranking

rand_bv = on_regex(r"^(随机)?(迪拉熊|dlx)(视频|sp|v)$", re.I)
add_bv = on_regex(r"^(加视频|jsp)(\s*BV[A-Za-z0-9]{10})+$", re.I, permission=ADMIN)
remove_bv = on_regex(r"^(删视频|jsp)(\s*BV[A-Za-z0-9]{10})+$", re.I, permission=ADMIN)

LIMIT_MINUTES = 2
LIMIT_TIMES = 6

groups: dict[int, list[datetime]] = dict()


@rand_bv.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    qq = event.get_user_id()
    while True:
        bvid = await bvidList.random_bvid()
        headers = {"User-Agent": f"kumabot/{config.version[0]}.{config.version[1]}"}
        async with AsyncClient(http2=True, follow_redirects=True) as session:
            resp = await session.get(
                URL("https://api.bilibili.com/x/web-interface/wbi/view"),
                params={"bvid": bvid},
                headers=headers,
            )
            if resp.is_error:
                resp.raise_for_status()
            video_info = resp.json()
        if video_info["code"] != 0:
            await bvidList.remove(bvid)
            continue

        break

    mini_app_ark = await bot.call_api(
        api="get_mini_app_ark",
        type="bili",
        title=video_info["data"]["title"],
        desc=video_info["data"]["desc"],
        picUrl=video_info["data"]["pic"],
        jumpUrl=f"pages/video/video?bvid={bvid}",
        webUrl=f"https://www.bilibili.com/video/{bvid}/",
    )
    await rand_bv.send(MessageSegment.json(json.dumps(mini_app_ark["data"]).decode()))
    await ranking.update_count(qq=qq, type="video")

    star, method, extend = await stars.give_rewards(
        qq, 5, 25, "欣赏迪拉熊视频", event.time
    )
    msg = f"迪拉熊奖励你{star}颗★mai~"
    match method & 0b1111:
        case 0b0010:
            msg += "All perfect plus!"
        case 0b0011:
            msg += f"人品大爆发，迪拉熊额外给你{extend}颗★哦~"
    if method & 0b0001_0000:
        msg += f"今日首次奖励，迪拉熊额外给你{extend}颗★哦~"
    await rand_bv.send(msg, at_sender=True)

    groups.setdefault(group_id, list())
    now = datetime.fromtimestamp(event.time, timezone(timedelta(hours=8)))
    while len(groups[group_id]) > 0:
        t = groups[group_id][0]
        if now - t < timedelta(minutes=LIMIT_MINUTES):
            break

        groups[group_id].pop(0)

    if len(groups[group_id]) >= LIMIT_TIMES:
        msg = MessageSegment.text("迪拉熊提醒你：注意不要过度刷屏，给别人带来困扰mai~")
        await rand_bv.send(msg, at_sender=True)

    groups[group_id].append(now)


@add_bv.handle()
async def _(event: MessageEvent):
    msg = event.get_plaintext()
    bvids = re.findall(r"BV[A-Za-z0-9]{10}", msg)
    for bvid in bvids:
        await bvidList.add(bvid)
    await add_bv.finish(MessageSegment.text("已添加"))


@remove_bv.handle()
async def _(event: MessageEvent):
    msg = event.get_plaintext()
    bvids = re.findall(r"BV[A-Za-z0-9]{10}", msg)
    for bvid in bvids:
        await bvidList.remove(bvid)
    await remove_bv.finish(MessageSegment.text("已删除"))
