import re
from pathlib import Path

from nonebot import on_regex
from nonebot.adapters.onebot.v11 import MessageSegment

all_help = on_regex(r"^((迪拉熊|dlx)(help|指令|帮助)|指令大全)$", re.I)
report = on_regex(r"(迪拉熊|dlx)(有|出)?(问题|bug)", re.I)


@all_help.handle()
async def _():
    msg = MessageSegment.image(Path("./Static/Help/0.png"))
    await all_help.send(msg)


@report.handle()
async def _():
    msg = (
        MessageSegment.text("迪拉熊Bug反馈&建议收集站：https://l.srcz.one/kumabugs"),
        MessageSegment.image(Path("./Static/Help/1.jpg")),
        MessageSegment.text("git仓库：https://codeberg.org/Derakkuma"),
    )
    await report.send(msg)
