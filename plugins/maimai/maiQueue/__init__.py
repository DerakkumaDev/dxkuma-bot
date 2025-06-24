import re

from nonebot import on_regex
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent

from .database import arcadeManager
from .utils import gen_message

registering = on_regex(r"^注册机厅\s*.+$", re.I)
binding = on_regex(r"^绑定机厅\s*.+$", re.I)
unbinding = on_regex(r"^解绑机厅\s*.+$", re.I)
search = on_regex(r"^搜索机厅\s*.+$", re.I)
add_alias = on_regex(r"^添加别名\s*.+?\s+.+$", re.I)
remove_alias = on_regex(r"^删除别名\s*.+?\s+.+$", re.I)
list_count = on_regex(r"^(机厅|jt|.+\s*)有?(几(人|卡)?|多少(人|卡)|jr?)$", re.I)
change_count = on_regex(r"^.+\s*([加减为＋－＝\+-=])\s*\d+(人|卡)?$", re.I)


@registering.handle()
async def _(event: GroupMessageEvent):
    group_id = event.group_id
    msg = event.get_plaintext()
    match = re.fullmatch(r"注册机厅\s*(.+)", msg)
    if not match:
        return

    name = match.group(1)
    arcade_id = arcadeManager.create(name)
    if arcade_id is None:
        await registering.finish("已创建过该机厅", at_sender=True)

    if not arcadeManager.bind(group_id, arcade_id):
        await registering.finish("成功创建机厅，但绑定失败", at_sender=True)

    await registering.send("成功创建并绑定机厅", at_sender=True)


@binding.handle()
async def _(event: GroupMessageEvent):
    group_id = event.group_id
    msg = event.get_plaintext()
    match = re.fullmatch(r"绑定机厅\s*(.+)", msg)
    if not match:
        return

    name = match.group(1)
    arcade_id = arcadeManager.get_arcade_id(name)
    if arcade_id is None:
        await binding.finish("找不到机厅", at_sender=True)

    if not arcadeManager.bind(group_id, arcade_id):
        await binding.finish("已绑定过该机厅", at_sender=True)

    await binding.send("成功绑定机厅", at_sender=True)


@unbinding.handle()
async def _(event: GroupMessageEvent):
    group_id = event.group_id
    msg = event.get_plaintext()
    match = re.fullmatch(r"解绑机厅\s*(.+)", msg)
    if not match:
        return

    word = match.group(1)
    matching_arcade = arcadeManager.search(group_id, word)
    matching_arcade_count = len(matching_arcade)
    if matching_arcade_count < 1:
        await unbinding.finish("找不到机厅", at_sender=True)

    if matching_arcade_count > 1:
        await unbinding.finish("关键词过于模糊", at_sender=True)

    arcade_id = matching_arcade[0]
    if not arcadeManager.unbind(group_id, arcade_id):
        await unbinding.finish("找不到机厅", at_sender=True)

    await unbinding.send("成功解绑机厅", at_sender=True)


@search.handle()
async def _(event: GroupMessageEvent):
    msg = event.get_plaintext()
    match = re.fullmatch(r"搜索机厅\s*(.+)", msg)
    if not match:
        return

    word = match.group(1)
    matching_arcade_ids = arcadeManager.search_all(word)
    matching_arcade_count = len(matching_arcade_ids)
    if matching_arcade_count < 1:
        await search.finish("找不到机厅", at_sender=True)

    await search.send(
        f"找到以下机厅：\r\n{"\r\n".join([arcadeManager.get_arcade(arcade_id)["name"] for arcade_id in matching_arcade_ids])}",
        at_sender=True,
    )


@add_alias.handle()
async def _(event: GroupMessageEvent):
    group_id = event.group_id
    msg = event.get_plaintext()
    match = re.fullmatch(r"添加别名\s*(.+?)\s+(.+)", msg)
    if not match:
        return

    name = match.group(1)
    alias = match.group(2)
    arcade_id = arcadeManager.get_arcade_id(name)
    if arcade_id is None:
        await add_alias.finish("找不到机厅", at_sender=True)

    bounden_arcade_ids = arcadeManager.get_bounden_arcade_ids(group_id)
    if arcade_id not in bounden_arcade_ids:
        await add_alias.finish("找不到机厅", at_sender=True)

    if not arcadeManager.add_ailas(arcade_id, alias):
        await add_alias.finish("已存在该别名", at_sender=True)

    await add_alias.send("成功添加别名", at_sender=True)


@remove_alias.handle()
async def _(event: GroupMessageEvent):
    group_id = event.group_id
    msg = event.get_plaintext()
    match = re.fullmatch(r"删除别名\s*(.+?)\s+(.+)", msg)
    if not match:
        return

    name = match.group(1)
    alias = match.group(2)
    arcade_id = arcadeManager.get_arcade_id(name)
    if arcade_id is None:
        await remove_alias.finish("找不到机厅", at_sender=True)

    bounden_arcade_ids = arcadeManager.get_bounden_arcade_ids(group_id)
    if arcade_id not in bounden_arcade_ids:
        await remove_alias.finish("找不到机厅", at_sender=True)

    if not arcadeManager.remove_ailas(arcade_id, alias):
        await remove_alias.finish("找不到别名", at_sender=True)

    await remove_alias.send("成功删除别名", at_sender=True)


@list_count.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    msg = event.get_plaintext()
    match = re.fullmatch(
        r"(?:机厅|jt|(.+)\s*)有?(?:几(?:人|卡)?|多少(?:人|卡)|jr?)", msg
    )
    arcade_ids = None
    if match:
        word = match.group(1)
        if word is not None:
            arcade_ids = arcadeManager.search(group_id, word)
            matching_arcade_count = len(arcade_ids)
            if matching_arcade_count < 1:
                return

            if matching_arcade_count > 1:
                return

    if arcade_ids is None:
        arcade_ids = arcadeManager.get_bounden_arcade_ids(group_id)

    if len(arcade_ids) < 1:
        await list_count.finish("找不到机厅", at_sender=True)

    await list_count.send(
        f"\r\n{"\r\n\r\n".join([await gen_message(bot, arcade_id) for arcade_id in arcade_ids])}",
        at_sender=True,
    )


@change_count.handle()
async def _(event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    msg = event.get_plaintext()
    match = re.fullmatch(r"(.+)\s*([加减为＋－＝\+-=])\s*(\d+)(?:人|卡)?", msg)
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

    matching_arcade = arcadeManager.search(group_id, word)
    matching_arcade_count = len(matching_arcade)
    if matching_arcade_count < 1:
        return

    if matching_arcade_count > 1:
        return

    arcade_id = matching_arcade[0]
    arcade = arcadeManager.do_action(
        arcade_id, action, group_id, user_id, event.time, int(num)
    )
    await change_count.send(
        f"{arcade["name"]}已变更为{arcade["count"]}卡", at_sender=True
    )
