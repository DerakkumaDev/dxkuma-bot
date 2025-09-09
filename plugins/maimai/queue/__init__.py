import re

from nonebot import on_regex
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent

from util.permission import ADMIN
from .database import arcadeManager
from .utils import gen_message

all_help = on_regex(r"^(迪拉熊|dlx)([cp]k|[查排]卡)$", re.I)
registering = on_regex(r"^注册机厅\s*.+$")
binding = on_regex(r"^绑定机厅\s*.+$")
unbinding = on_regex(r"^解绑机厅\s*.+$")
search = on_regex(r"^搜索机厅\s*.+$")
list_all = on_regex(r"^(所有|全部)机厅$", permission=ADMIN)
add_alias = on_regex(r"^添加别(名|称)\s*.+?\s+.+$")
remove_alias = on_regex(r"^删除别(名|称)\s*.+?\s+.+$")
list_count = on_regex(r"^(机厅|jt|看看|.+\s*)?有?(几(人|卡)?|多少(人|卡)|jr?)$", re.I)
change_count = on_regex(
    r"^.+\s*(加|减|为|＋|－|＝|\+|-|=)?\s*\d+(人|卡)?$", block=False
)


@all_help.handle()
async def _(event: GroupMessageEvent):
    await all_help.send(
        "一起来舞萌吧~\r\n"
        "\r\n"
        "发送“注册机厅[机厅全称]”注册并为本群绑定机厅\r\n"
        "发送“绑定机厅[机厅全称]”为本群绑定机厅\r\n"
        "发送“解绑机厅[别名]”为本群解绑机厅\r\n"
        "发送“搜索机厅[关键词]”搜索所有相关机厅\r\n"
        "发送“添加别名[机厅全称] [机厅别名]”为机厅添加别名\r\n"
        "发送“删除别名[机厅全称] [机厅别名]”为机厅删除别名\r\n"
        "发送“机厅有几卡”查询本群机厅卡数\r\n"
        "发送“[别名]有几卡”查询指定机厅卡数\r\n"
        "发送“[别名]（+/-/=）[整数]”更新指定机厅卡数\r\n"
        "\r\n"
        "每天4点（UTC+8）迪拉熊会帮大家清零卡数哦~不用谢mai~（骄傲）"
    )


@registering.handle()
async def _(event: GroupMessageEvent):
    group_id = event.group_id
    msg = event.get_plaintext()
    match = re.fullmatch(r"注册机厅\s*(.+)", msg)
    if not match:
        return

    name = match.group(1)
    arcade_id = await arcadeManager.create(name)
    if arcade_id is None:
        await registering.finish("这个机厅已经创建过了mai~", at_sender=True)

    if not await arcadeManager.bind(group_id, arcade_id):
        await registering.finish(
            "迪拉熊帮你创建了这个机厅，但是绑定失败了mai~", at_sender=True
        )

    await registering.send("迪拉熊帮你创建并绑定了这个机厅mai~", at_sender=True)


@binding.handle()
async def _(event: GroupMessageEvent):
    group_id = event.group_id
    msg = event.get_plaintext()
    match = re.fullmatch(r"绑定机厅\s*(.+)", msg)
    if not match:
        return

    name = match.group(1)
    arcade_id = await arcadeManager.get_arcade_id(name)
    if arcade_id is None:
        await binding.finish("迪拉熊没有找到这个机厅mai~", at_sender=True)

    if not await arcadeManager.bind(group_id, arcade_id):
        await binding.finish("迪拉熊已经帮你绑定过这个机厅了mai~", at_sender=True)

    await binding.send("迪拉熊帮你绑定了这个机厅mai~", at_sender=True)


@unbinding.handle()
async def _(event: GroupMessageEvent):
    group_id = event.group_id
    msg = event.get_plaintext()
    match = re.fullmatch(r"解绑机厅\s*(.+)", msg)
    if not match:
        return

    word = match.group(1)
    matching_arcade = await arcadeManager.search(group_id, word)
    matching_arcade_count = len(matching_arcade)
    if matching_arcade_count < 1:
        await unbinding.finish("迪拉熊没有找到这个机厅mai~", at_sender=True)

    if matching_arcade_count > 1:
        await unbinding.finish("结果太多啦，缩小范围再试试吧~", at_sender=True)

    arcade_id = matching_arcade[0]
    if not await arcadeManager.unbind(group_id, arcade_id):
        await unbinding.finish("迪拉熊没有找到这个机厅mai~", at_sender=True)

    await unbinding.send("迪拉熊帮你解绑了这个机厅mai~", at_sender=True)


@list_all.handle()
async def _(bot: Bot):
    all_arcade_ids = await arcadeManager.all_arcade_ids()
    all_arcade_count = len(all_arcade_ids)
    if all_arcade_count < 1:
        await list_all.finish("无机厅", at_sender=True)

    arcades = [
        await arcadeManager.get_arcade(arcade_id) for arcade_id in all_arcade_ids
    ]
    if len(arcades) < 1:
        await list_all.finish("无机厅", at_sender=True)

    arcade_names = [
        f"{arcade['name']}\r\n"
        f"ID：{arcade['id']}\r\n"
        f"绑定：{'、'.join(str(i) for i in arcade['bindings'])}\r\n"
        f"{
            f'别名：{"、".join(arcade["aliases"])}\r\n'
            if len(arcade['aliases']) > 0
            else str()
        }"
        f"{await gen_message(bot, arcade)}"
        for arcade in arcades
        if arcade is not None
    ]
    if len(arcade_names) < 1:
        await list_all.finish("无机厅", at_sender=True)

    await list_all.send(
        f"找到以下机厅：\r\n{'\r\n\r\n'.join(arcade_names)}",
        at_sender=True,
    )


@search.handle()
async def _(event: GroupMessageEvent):
    msg = event.get_plaintext()
    match = re.fullmatch(r"搜索机厅\s*(.+)", msg)
    if not match:
        return

    word = match.group(1)
    matching_arcade_ids = await arcadeManager.search_all(word)
    matching_arcade_count = len(matching_arcade_ids)
    if matching_arcade_count < 1:
        await search.finish("迪拉熊没有找到对得上的机厅mai~", at_sender=True)

    if matching_arcade_count > 10:
        await search.finish("结果太多啦，缩小范围再试试吧~", at_sender=True)

    arcades = [
        await arcadeManager.get_arcade(arcade_id) for arcade_id in matching_arcade_ids
    ]
    if len(arcades) < 1:
        await search.finish("迪拉熊没有找到对得上的机厅mai~", at_sender=True)

    arcade_names = [
        f"{arcade['name']}{
            f'\r\n别名：{"、".join(arcade["aliases"])}'
            if len(arcade['aliases']) > 0
            else str()
        }"
        for arcade in arcades
        if arcade is not None
    ]
    if len(arcade_names) < 1:
        await search.finish("迪拉熊没有找到对得上的机厅mai~", at_sender=True)

    await search.send(
        f"迪拉熊找到了这些机厅——\r\n{'\r\n\r\n'.join(arcade_names)}",
        at_sender=True,
    )


@add_alias.handle()
async def _(event: GroupMessageEvent):
    group_id = event.group_id
    msg = event.get_plaintext()
    match = re.fullmatch(r"添加别(?:名|称)\s*(.+?)\s+(.+)", msg)
    if not match:
        return

    name = match.group(1)
    alias = match.group(2)
    arcade_id = await arcadeManager.get_arcade_id(name)
    if arcade_id is None:
        await add_alias.finish("迪拉熊没有找到对得上的机厅mai~", at_sender=True)

    bounden_arcade_ids = await arcadeManager.get_bounden_arcade_ids(group_id)
    if arcade_id not in bounden_arcade_ids:
        await add_alias.finish("迪拉熊没有找到对得上的机厅mai~", at_sender=True)

    if not await arcadeManager.add_alias(arcade_id, alias):
        await add_alias.finish("迪拉熊已经帮你添加过这个别名了mai~", at_sender=True)

    await add_alias.send("迪拉熊帮你添加了这个别名mai~", at_sender=True)


@remove_alias.handle()
async def _(event: GroupMessageEvent):
    group_id = event.group_id
    msg = event.get_plaintext()
    match = re.fullmatch(r"删除别(?:名|称)\s*(.+?)\s+(.+)", msg)
    if not match:
        return

    name = match.group(1)
    alias = match.group(2)
    arcade_id = await arcadeManager.get_arcade_id(name)
    if arcade_id is None:
        await remove_alias.finish("迪拉熊没有找到对得上的机厅mai~", at_sender=True)

    bounden_arcade_ids = await arcadeManager.get_bounden_arcade_ids(group_id)
    if arcade_id not in bounden_arcade_ids:
        await remove_alias.finish("迪拉熊没有找到对得上的机厅mai~", at_sender=True)

    if not await arcadeManager.remove_alias(arcade_id, alias):
        await remove_alias.finish("迪拉熊没有找到对得上的别名mai~", at_sender=True)

    await remove_alias.send("迪拉熊帮你删除了这个别名mai~", at_sender=True)


@list_count.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    msg = event.get_plaintext()
    match = re.fullmatch(
        r"(?:机厅|jt|看看|(.+?)\s*)?有?(?:几(?:人|卡)?|多少(?:人|卡)|jr?)", msg
    )
    arcade_ids = None
    if match:
        word = match.group(1)
        if word is not None:
            arcade_ids = await arcadeManager.search(group_id, word)
            matching_arcade_count = len(arcade_ids)
            if matching_arcade_count < 1:
                return

            if matching_arcade_count > 1:
                return

    if arcade_ids is None:
        arcade_ids = await arcadeManager.get_bounden_arcade_ids(group_id)

    if len(arcade_ids) < 1:
        return

    messages = [
        f"{arcade['name']}\r\n{await gen_message(bot, arcade)}"
        for arcade in [
            await arcadeManager.get_arcade(arcade_id) for arcade_id in arcade_ids
        ]
        if arcade is not None
    ]
    if len(messages) < 1:
        return

    await list_count.send(f"\r\n{'\r\n\r\n'.join(messages)}", at_sender=True)


@change_count.handle()
async def _(event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    msg = event.get_plaintext()
    match = re.fullmatch(r"(.+?)\s*(加|减|为|＋|－|＝|\+|-|=)?\s*(\d+)(?:人|卡)?", msg)
    if not match:
        return

    word = match.group(1)
    action_str = match.group(2)
    num = match.group(3)
    match action_str:
        case "加":
            action = "add"
        case "＋":
            action = "add"
        case "+":
            action = "add"
        case "减":
            action = "remove"
        case "－":
            action = "remove"
        case "-":
            action = "remove"
        case "为":
            action = "set"
        case "＝":
            action = "set"
        case "=":
            action = "set"
        case None:
            action = "set"
        case _:
            return

    matching_arcade = await arcadeManager.search(group_id, word)
    matching_arcade_count = len(matching_arcade)
    if matching_arcade_count < 1:
        return

    if matching_arcade_count > 1:
        return

    arcade_id = matching_arcade[0]
    arcade = await arcadeManager.do_action(
        arcade_id, action, group_id, user_id, event.time, int(num)
    )

    await change_count.send(
        f"迪拉熊帮你把{arcade['name']}的卡数改成了{arcade['count']}mai~", at_sender=True
    )
