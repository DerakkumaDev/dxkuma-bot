import re
from pathlib import Path

from nonebot import on_regex
from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot.rule import to_me


all_help = on_regex(r"^((迪拉熊|dlx)(help|指令|帮助)|指令大全)$", re.I)
report = on_regex(r"(迪拉熊|dlx)(有|出)?(问题|bug)", re.I)
report_tome = on_regex(r"问题|bug", re.I, to_me())


@all_help.handle()
async def _():
    msg = (
        MessageSegment.image(Path("./Static/Help/0.png")),
        MessageSegment.text("公开测试群：959231211"),
    )
    await all_help.send(msg)


@report.handle()
async def _():
    msg = (
        MessageSegment.text("http://sl.srcz.one/kumabugs"),
        MessageSegment.image(Path("./Static/Help/1.jpg")),
    )
    await report.send(msg)


@report_tome.handle()
async def _():
    msg = (
        MessageSegment.text("http://sl.srcz.one/kumabugs"),
        MessageSegment.image(Path("./Static/Help/1.jpg")),
    )
    await report_tome.send(msg)
