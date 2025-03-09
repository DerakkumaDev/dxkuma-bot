import math
import os
import re
import shelve
import time
from pathlib import Path

import aiohttp
from dill import Pickler, Unpickler
from nonebot import on_fullmatch, on_message, on_regex
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment, Bot
from numpy import random

from util.Data import (
    get_chart_stats,
    get_music_data,
    get_alias_list_lxns,
    get_alias_list_ycn,
    get_alias_list_xray,
)
from util.DivingFish import get_player_data, get_player_records, get_player_record
from util.Rule import regex
from .GenBests import (
    compute_record,
    generatebests,
    generate_wcb,
    get_page_records,
    ratings,
    records_filter,
    find_song_by_id,
    dxscore_proc,
    get_fit_diff,
)
from .MusicInfo import music_info, play_info, utage_music_info, score_info

shelve.Pickler = Pickler
shelve.Unpickler = Unpickler

best50 = on_message(regex(r"^dlxb?50$", re.I))
best40 = on_message(regex(r"^dlxb?40$", re.I))
fit50 = on_fullmatch("dlxf50", ignorecase=True)
dxs50 = on_fullmatch("dlxs50", ignorecase=True)
star50 = on_message(regex(r"^dlxx50(\s*[1-5])+$", re.I))
rate50 = on_message(regex(r"^dlxr50(\s*(s{1,3}(p|\+)?|a{1,3}|b{1,3}|[cd]))+?$", re.I))
ap50 = on_message(regex(r"^dlxap(50)?$", re.I))
fc50 = on_message(regex(r"^dlxfc(50)?$", re.I))
cf50 = on_message(regex(r"^dlxcf(50)?$", re.I))
sd50 = on_message(regex(r"^dlx(s|f)d(50)?$", re.I))
all50 = on_message(regex(r"^dlx(all?(50)?|b)$", re.I))
rr50 = on_regex(r"^dlxrr(50)?(\s*\d+)?$", re.I)
sunlist = on_regex(r"^dlx(sunn?|cun|寸|🤏)(\s*\d+?)?$", re.I)
locklist = on_regex(r"^dlx(suo|锁|🔒)(\s*\d+?)?$", re.I)

songinfo = on_regex(r"^(chart|id)\s*((dx|sd|标准?)\s*)?.+$", re.I)
playinfo = on_regex(r"^(score|info)\s*((dx|sd|标准?)\s*)?.+$", re.I)
scoreinfo = on_regex(
    r"^(detail|分数表)\s*(绿|黄|红|紫|白)\s*((dx|sd|标准?)\s*)?.+$", re.I
)
playaudio = on_regex(r"^dlx点歌\s*.+$", re.I)
randomsong = on_regex(r"^随(歌|个|首|张)\s*(绿|黄|红|紫|白)?\s*\d+(\.\d|\+)?$")
maiwhat = on_fullmatch("mai什么", ignorecase=True)

wcb = on_regex(
    r"^(list|完成表)\s*(\d+(\.\d|\+)?|真|超|檄|橙|晓|桃|樱|紫|堇|白|雪|辉|舞|熊|华|爽|煌|宙|星|祭|祝|双)(\s*\d+)?$",
    re.I,
)

whatSong = on_regex(
    r"^((search|查歌)\s*((dx|sd|标准?)\s*)?.+|((dx|sd|标准?)\s*)?.+是什么歌？?)$", re.I
)
aliasSearch = on_regex(r"^((alias|查看?别名)\s*.+|.+有(什么|哪些)别名？?)$")

all_plate = on_regex(r"^(plate|看姓名框)$", re.I)
all_frame = on_regex(r"^(frame|看背景)$", re.I)

set_plate = on_regex(r"^(setplate|设置?姓名框)\s*\d{6}$", re.I)
set_frame = on_regex(r"^(setframe|设置?背景)\s*\d{6}$", re.I)

ratj_on = on_regex(r"^(开启?|启用)分数推荐$")
ratj_off = on_regex(r"^(关闭?|禁用)分数推荐$")

allow_other_on = on_regex(r"^(开启?|启用|允许)代查$")
allow_other_off = on_regex(r"^(关闭?|禁用|禁止)代查$")


# 根据乐曲别名查询乐曲id列表
async def find_songid_by_alias(name, song_list):
    # 芝士id列表
    matched_ids = list()

    # 芝士查找
    for info in song_list:
        if name.casefold() == info["title"].casefold() or name == info["id"]:
            matched_ids.append(info["id"])

    if matched_ids:
        return matched_ids

    alias_list = await get_alias_list_lxns()
    for info in alias_list["aliases"]:
        song_id = str(info["song_id"])
        if song_id in matched_ids:
            continue
        for alias in info["aliases"]:
            if name.casefold() == alias.casefold():
                matched_ids.append(song_id)
                break

    alias_list = await get_alias_list_xray()
    for id, info in alias_list.items():
        song_id = str(id)
        if song_id in matched_ids:
            continue
        for alias in info:
            if name.casefold() == alias.casefold():
                matched_ids.append(song_id)
                break

    alias_list = await get_alias_list_ycn()
    for info in alias_list["content"]:
        song_id = str(info["SongID"])
        if song_id in matched_ids:
            continue
        for alias in info["Alias"]:
            if name.casefold() == alias.casefold():
                matched_ids.append(song_id)
                break

    # 芝士排序
    # sorted_matched_ids = sorted(matched_ids, key=int)

    # 芝士输出
    return matched_ids


async def records_to_bests(
    records: list | None,
    songList,
    fc_rules: list | None = None,
    rate_rules: list | None = None,
    is_fit: bool = False,
    is_sd: bool = False,
    is_dxs: bool = False,
    is_all: bool = False,
    is_old: bool = False,
    dx_star_count: str | None = None,
    rating: int = 0,
):
    sd = list()
    dx = list()
    charts = await get_chart_stats()
    mask_enabled = False
    if not records:
        for song in songList:
            if len(song["id"]) > 5:
                continue
            for i, j in enumerate(song["ds"]):
                record = {
                    "achievements": 101,
                    "ds": j,
                    "dxScore": sum(song["charts"][i]["notes"]) * 3,
                    "fc": "fsdp",
                    "fs": "app",
                    "level": "",
                    "level_index": i,
                    "level_label": [
                        "Basic",
                        "Advanced",
                        "Expert",
                        "Master",
                        "Re:MASTER",
                    ][i],
                    "ra": math.trunc(j * 22.512),
                    "rate": "sssp",
                    "song_id": int(song["id"]),
                    "title": song["title"],
                    "type": song["type"],
                }
                if song["basic_info"]["is_new"]:
                    dx.append(record)
                else:
                    sd.append(record)
        sd.sort(key=lambda x: (x["ra"], x["ds"], x["achievements"]), reverse=True)
        dx.sort(key=lambda x: (x["ra"], x["ds"], x["achievements"]), reverse=True)
        if rating:
            while (
                sum(d["ra"] for d in sd[:35]) + sum(d["ra"] for d in dx[:15]) > rating
            ):
                if (dx and sd and dx[0]["ra"] > sd[0]["ra"]) or (dx and not sd):
                    b = dx
                elif sd:
                    b = sd
                b.pop(0)
        return sd[:35], dx[:15], False
    for record in records:
        if record["level_label"] == "Utage":
            continue
        if fc_rules and record["fc"] not in fc_rules:
            continue
        if rate_rules and record["rate"] not in rate_rules:
            continue
        song_id = str(record["song_id"])
        song_data = [d for d in songList if d["id"] == song_id][0]
        is_new = song_data["basic_info"]["is_new"]
        fit_diff = get_fit_diff(song_id, record["level_index"], record["ds"], charts)
        if is_fit:
            if record["ra"] == 0:
                continue
            if record["achievements"] > 0 and record["dxScore"] == 0:
                mask_enabled = True
                continue
            record["s_ra"] = record["ds"]
            record["ds"] = math.trunc(fit_diff * 100) / 100
            record["ra"] = math.trunc(
                fit_diff
                * (record["achievements"] if record["achievements"] < 100.5 else 100.5)
                * get_ra_in(record["rate"])
                / 100
            )
        if is_sd:
            record["diff"] = (
                charts["charts"][song_id][record["level_index"]]["std_dev"]
                if song_id in charts["charts"]
                else 0.0
            )
        if is_dxs:
            if record["achievements"] > 0 and record["dxScore"] == 0:
                mask_enabled = True
                continue
            if not dx_star_count:
                song_data = find_song_by_id(song_id, songList)
                record["achievements"] = (
                    record["dxScore"]
                    / (sum(song_data["charts"][record["level_index"]]["notes"]) * 3)
                    * 101
                )
                record["ra"] = math.trunc(
                    record["ds"]
                    * record["achievements"]
                    * get_ra_in(record["rate"])
                    / 100
                )
            else:
                sum_dxscore = (
                    sum(song_data["charts"][record["level_index"]]["notes"]) * 3
                )
                _, stars = dxscore_proc(record["dxScore"], sum_dxscore)
                if str(stars) not in dx_star_count:
                    continue
        if is_old:
            record["ra"] = math.trunc(
                record["ds"]
                * (record["achievements"] if record["achievements"] < 100.5 else 100.5)
                * get_ra_in_old(record["rate"])
                / 100
            )
        if record["ra"] == 0 or record["achievements"] > 101:
            continue
        if is_new or is_all:
            b = dx
        else:
            b = sd
        b.append(record)
    if is_all:
        all_records = sorted(
            dx, key=lambda x: (x["ra"], x["ds"], x["achievements"]), reverse=True
        )
        dx.clear()
        for record in [
            i
            for i in all_records
            if i["ra"]
            >= all_records[49 if len(all_records) > 50 else len(all_records) - 1]["ra"]
        ]:
            song_id = str(record["song_id"])
            song_data = [d for d in songList if d["id"] == song_id][0]
            is_new = song_data["basic_info"]["is_new"]
            if is_new:
                if len(dx) < 15:
                    dx.append(record)
                    all_records.remove(record)
            elif len(sd) < 35:
                sd.append(record)
                all_records.remove(record)
            if len(dx) >= 15 and len(sd) >= 35:
                break
        else:
            for i in all_records:
                if len(sd) < 35:
                    b = sd
                elif len(dx) < 15:
                    b = dx
                else:
                    break
                b.append(i)
        return sd, dx, mask_enabled
    if is_sd:
        k = lambda x: (x["ra"] * x["diff"], x["ra"], x["ds"], x["achievements"])
    else:
        k = lambda x: (x["ra"], x["ds"], x["achievements"])
    b35 = sorted(sd, key=k, reverse=True)[: 25 if is_old else 35]
    b15 = sorted(dx, key=k, reverse=True)[:15]
    return b35, b15, mask_enabled


async def compare_bests(sender_records, target_records, songList):
    handle_type = len(sender_records) > len(target_records)
    sd = list()
    dx = list()
    mask_enabled = False
    b35, b15, mask_enabled = await records_to_bests(sender_records, songList)
    if not b35 and not b15:
        return sd, dx, mask_enabled
    sd_min = b35[-1]["ra"] if b35 else -1
    dx_min = b15[-1]["ra"] if b15 else -1
    for record in target_records if handle_type else sender_records:
        if record["level_label"] == "Utage":
            continue
        if record["ra"] == 0 or record["achievements"] > 101:
            continue
        if record["achievements"] > 0 and record["dxScore"] == 0:
            mask_enabled = True
            continue
        other_record = [
            d
            for d in (sender_records if handle_type else target_records)
            if d["song_id"] == record["song_id"]
            and d["level_index"] == record["level_index"]
        ]
        if not other_record:
            continue
        other_record = other_record[0]
        if other_record["ra"] == 0 or other_record["achievements"] > 101:
            continue
        if other_record["achievements"] > 0 and other_record["dxScore"] == 0:
            mask_enabled = True
            continue
        song_id = str(record["song_id"])
        song_data = [d for d in songList if d["id"] == song_id][0]
        is_new = song_data["basic_info"]["is_new"]
        if handle_type:
            record["preferred"] = record["ra"] >= (dx_min if is_new else sd_min)
            record["s_ra"] = other_record["ra"]
            if is_new:
                dx.append(record)
            else:
                sd.append(record)
        else:
            other_record["preferred"] = other_record["ra"] >= (
                dx_min if is_new else sd_min
            )
            other_record["s_ra"] = record["ra"]
            if is_new:
                dx.append(other_record)
            else:
                sd.append(other_record)
    b35 = sorted(
        sd,
        key=lambda x: (x["preferred"], x["ra"] - x["s_ra"], x["ds"], x["achievements"]),
        reverse=True,
    )[:35]
    b15 = sorted(
        dx,
        key=lambda x: (x["preferred"], x["ra"] - x["s_ra"], x["ds"], x["achievements"]),
        reverse=True,
    )[:15]
    return b35, b15, mask_enabled


def get_ra_in(rate: str) -> float:
    return ratings[rate][1]


def get_ra_in_old(rate: str) -> float:
    return ratings[rate][2]


async def get_info_by_name(name, music_type, songList):
    rep_ids = await find_songid_by_alias(name, songList)
    if not rep_ids:
        return 2, None
    for song_id in rep_ids.copy():
        song_info = find_song_by_id(song_id, songList)
        if not song_info:
            rep_ids.remove(song_id)
            continue

        id_int = int(song_id)
        if music_type:
            if music_type.casefold() == "dx":
                if song_info["type"] != "DX":
                    rep_ids.remove(song_id)
            elif (
                music_type.casefold() == "sd"
                or music_type == "标准"
                or music_type == "标"
            ):
                if song_info["type"] != "SD":
                    rep_ids.remove(song_id)
        elif song_info["type"] != "DX" or str(id_int % 10000) not in rep_ids:
            other_id = str(id_int + 10000)
            if other_id in rep_ids:
                continue
            other_info = find_song_by_id(other_id, songList)
            if other_info:
                rep_ids.append(other_id)
    if not rep_ids:
        return 2, None
    elif len(rep_ids) > 20:
        return 3, rep_ids
    elif len(rep_ids) > 1:
        output_lst = set()
        for song_id in sorted(rep_ids, key=int):
            song_info = find_song_by_id(song_id, songList)
            song_title = song_info["title"]
            output_lst.add(song_title)

        return 1, output_lst if len(output_lst) > 1 else song_info

    song_info = find_song_by_id(rep_ids[0], songList)
    if not song_info:
        return 2, None

    return 0, song_info


@best50.handle()
async def _(bot: Bot, event: MessageEvent):
    sender_qq = event.user_id
    target_qq = event.get_user_id()
    user_info = await bot.get_stranger_info(user_id=target_qq)
    for message in event.get_message():
        if message.type != "at":
            continue
        target_qq = message.data["qq"]
        if target_qq == event.get_user_id():
            continue
        if target_qq == bot.self_id:
            return
        if "isBlock" not in user_info and "isBlocked" not in user_info:
            sender_qq = target_qq
            break
        else:
            with shelve.open("./data/user_config.db") as config:
                if (
                    target_qq not in config
                    or "allow_other" not in config[target_qq]
                    or config[target_qq]["allow_other"]
                ):
                    break
    else:
        if target_qq != event.get_user_id():
            msg = (
                MessageSegment.at(sender_qq),
                MessageSegment.text(" "),
                MessageSegment.text("他不允许其他人查询他的成绩"),
                MessageSegment.image(Path("./Static/Maimai/Function/3.png")),
            )
            await best50.finish(msg)
    data, status = await get_player_data(target_qq)
    if status == 400:
        msg = (
            MessageSegment.at(sender_qq),
            MessageSegment.text(" "),
            MessageSegment.text(
                f"迪拉熊没有找到{"你" if target_qq == event.get_user_id() else "他"}的信息"
            ),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await best50.finish(msg)
    elif status == 403:
        msg = (
            MessageSegment.at(sender_qq),
            MessageSegment.text(" "),
            MessageSegment.text(
                f"{"你" if target_qq == event.get_user_id() else "他"}在查分器启用了隐私或者没有同意查分器的用户协议"
            ),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await best50.finish(msg)
    elif not data:
        msg = (
            MessageSegment.at(sender_qq),
            MessageSegment.text(" "),
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/maimai/-1.png")),
        )
        await best50.finish(msg)
    songList = await get_music_data()
    charts = data["charts"]
    b35 = sorted(
        charts["sd"], key=lambda x: (x["ra"], x["ds"], x["achievements"]), reverse=True
    )
    b15 = sorted(
        charts["dx"], key=lambda x: (x["ra"], x["ds"], x["achievements"]), reverse=True
    )
    if not b35 and not b15:
        msg = (
            MessageSegment.at(sender_qq),
            MessageSegment.text(" "),
            MessageSegment.text(
                f"{"你" if target_qq == event.get_user_id() else "他"}没有上传任何成绩"
            ),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await best50.finish(msg)
    await best50.send(
        (
            MessageSegment.at(sender_qq),
            MessageSegment.text(" "),
            MessageSegment.text("迪拉熊绘制中，稍等一下mai~"),
        )
    )
    nickname = data["nickname"]
    dani = data["additional_rating"]
    with shelve.open("./data/user_config.db") as config:
        if target_qq not in config:
            frame = "200502"
            plate = "000101"
            is_rating_tj = True
        else:
            if "frame" not in config[target_qq]:
                frame = "200502"
            else:
                frame = config[target_qq]["frame"]
            if "plate" not in config[target_qq]:
                plate = "000101"
            else:
                plate = config[target_qq]["plate"]
            if "rating_tj" not in config[target_qq]:
                is_rating_tj = True
            else:
                is_rating_tj = config[target_qq]["rating_tj"]
    async with aiohttp.ClientSession(conn_timeout=3) as session:
        async with session.get(
            f"http://q.qlogo.cn/headimg_dl?dst_uin={target_qq}&spec=640&img_type=png"
        ) as resp:
            icon = await resp.read()
    start_time = time.perf_counter()
    img = await generatebests(
        b35=b35,
        b15=b15,
        nickname=nickname,
        dani=dani,
        type="b50",
        icon=icon,
        frame=frame,
        plate=plate,
        is_rating_tj=is_rating_tj,
        songList=songList,
    )
    end_time = time.perf_counter()
    msg = (
        MessageSegment.at(sender_qq),
        MessageSegment.image(img),
        MessageSegment.text(f"绘制用时：{end_time - start_time:.2f}秒"),
    )
    await best50.send(msg)


@ap50.handle()
async def _(bot: Bot, event: MessageEvent):
    target_qq = event.get_user_id()
    for message in event.get_message():
        if message.type != "at":
            continue
        target_qq = message.data["qq"]
        if target_qq == event.get_user_id():
            continue
        if target_qq == bot.self_id:
            return
        with shelve.open("./data/user_config.db") as config:
            if (
                target_qq not in config
                or "allow_other" not in config[target_qq]
                or config[target_qq]["allow_other"]
            ):
                break
    else:
        if target_qq != event.get_user_id():
            msg = (
                MessageSegment.text("他不允许其他人查询他的成绩"),
                MessageSegment.image(Path("./Static/Maimai/Function/3.png")),
            )
            await ap50.finish(msg, at_sender=True)
    data, status = await get_player_records(target_qq)
    if status == 400:
        msg = (
            MessageSegment.text(
                f"迪拉熊没有找到{"你" if target_qq == event.get_user_id() else "他"}的信息"
            ),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await ap50.finish(msg, at_sender=True)
    elif not data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/maimai/-1.png")),
        )
        await ap50.finish(msg, at_sender=True)
    records = data["records"]
    if not records:
        await ap50.finish(
            (
                MessageSegment.text(
                    f"{"你" if target_qq == event.get_user_id() else "他"}没有上传任何成绩"
                ),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    songList = await get_music_data()
    ap35, ap15, _ = await records_to_bests(records, songList, ["ap", "app"])
    if not ap35 and not ap15:
        await ap50.finish(
            (
                MessageSegment.text(
                    f"{"你" if target_qq == event.get_user_id() else "他"}没有全完美的成绩"
                ),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    await ap50.send(MessageSegment.text("迪拉熊绘制中，稍等一下mai~"), at_sender=True)
    nickname = data["nickname"]
    dani = data["additional_rating"]
    with shelve.open("./data/user_config.db") as config:
        if target_qq not in config:
            frame = "200502"
            plate = "000101"
            is_rating_tj = True
        else:
            if "frame" not in config[target_qq]:
                frame = "200502"
            else:
                frame = config[target_qq]["frame"]
            if "plate" not in config[target_qq]:
                plate = "000101"
            else:
                plate = config[target_qq]["plate"]
            if "rating_tj" not in config[target_qq]:
                is_rating_tj = True
            else:
                is_rating_tj = config[target_qq]["rating_tj"]
    async with aiohttp.ClientSession(conn_timeout=3) as session:
        async with session.get(
            f"http://q.qlogo.cn/headimg_dl?dst_uin={target_qq}&spec=640&img_type=png"
        ) as resp:
            icon = await resp.read()
    start_time = time.perf_counter()
    img = await generatebests(
        b35=ap35,
        b15=ap15,
        nickname=nickname,
        dani=dani,
        type="ap50",
        icon=icon,
        frame=frame,
        plate=plate,
        is_rating_tj=is_rating_tj,
        songList=songList,
    )
    end_time = time.perf_counter()
    msg = (
        MessageSegment.image(img),
        MessageSegment.text(f"绘制用时：{end_time - start_time:.2f}秒"),
    )
    await ap50.send(msg, at_sender=True)


@fc50.handle()
async def _(bot: Bot, event: MessageEvent):
    target_qq = event.get_user_id()
    for message in event.get_message():
        if message.type != "at":
            continue
        target_qq = message.data["qq"]
        if target_qq == event.get_user_id():
            continue
        if target_qq == bot.self_id:
            return
        with shelve.open("./data/user_config.db") as config:
            if (
                target_qq not in config
                or "allow_other" not in config[target_qq]
                or config[target_qq]["allow_other"]
            ):
                break
    else:
        if target_qq != event.get_user_id():
            msg = (
                MessageSegment.text("他不允许其他人查询他的成绩"),
                MessageSegment.image(Path("./Static/Maimai/Function/3.png")),
            )
            await fc50.finish(msg, at_sender=True)
    data, status = await get_player_records(target_qq)
    if status == 400:
        msg = (
            MessageSegment.text(
                f"迪拉熊没有找到{"你" if target_qq == event.get_user_id() else "他"}的信息"
            ),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await fc50.finish(msg, at_sender=True)
    elif not data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/maimai/-1.png")),
        )
        await fc50.finish(msg, at_sender=True)
    records = data["records"]
    if not records:
        await fc50.finish(
            (
                MessageSegment.text(
                    f"{"你" if target_qq == event.get_user_id() else "他"}没有上传任何成绩"
                ),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    songList = await get_music_data()
    fc35, fc15, _ = await records_to_bests(records, songList, ["fc", "fcp"])
    if not fc35 and not fc15:
        await fc50.finish(
            (
                MessageSegment.text(
                    f"{"你" if target_qq == event.get_user_id() else "他"}没有全连的成绩"
                ),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    await fc50.send(MessageSegment.text("迪拉熊绘制中，稍等一下mai~"), at_sender=True)
    nickname = data["nickname"]
    dani = data["additional_rating"]
    with shelve.open("./data/user_config.db") as config:
        if target_qq not in config:
            frame = "200502"
            plate = "000101"
            is_rating_tj = True
        else:
            if "frame" not in config[target_qq]:
                frame = "200502"
            else:
                frame = config[target_qq]["frame"]
            if "plate" not in config[target_qq]:
                plate = "000101"
            else:
                plate = config[target_qq]["plate"]
            if "rating_tj" not in config[target_qq]:
                is_rating_tj = True
            else:
                is_rating_tj = config[target_qq]["rating_tj"]
    async with aiohttp.ClientSession(conn_timeout=3) as session:
        async with session.get(
            f"http://q.qlogo.cn/headimg_dl?dst_uin={target_qq}&spec=640&img_type=png"
        ) as resp:
            icon = await resp.read()
    start_time = time.perf_counter()
    img = await generatebests(
        b35=fc35,
        b15=fc15,
        nickname=nickname,
        dani=dani,
        type="fc50",
        icon=icon,
        frame=frame,
        plate=plate,
        is_rating_tj=is_rating_tj,
        songList=songList,
    )
    end_time = time.perf_counter()
    msg = (
        MessageSegment.image(img),
        MessageSegment.text(f"绘制用时：{end_time - start_time:.2f}秒"),
    )
    await fc50.send(msg, at_sender=True)


@fit50.handle()
async def _(bot: Bot, event: MessageEvent):
    target_qq = event.get_user_id()
    for message in event.get_message():
        if message.type != "at":
            continue
        target_qq = message.data["qq"]
        if target_qq == event.get_user_id():
            continue
        if target_qq == bot.self_id:
            return
        with shelve.open("./data/user_config.db") as config:
            if (
                target_qq not in config
                or "allow_other" not in config[target_qq]
                or config[target_qq]["allow_other"]
            ):
                break
    else:
        if target_qq != event.get_user_id():
            msg = (
                MessageSegment.text("他不允许其他人查询他的成绩"),
                MessageSegment.image(Path("./Static/Maimai/Function/3.png")),
            )
            await fit50.finish(msg, at_sender=True)
    data, status = await get_player_records(target_qq)
    if status == 400:
        msg = (
            MessageSegment.text(
                f"迪拉熊没有找到{"你" if target_qq == event.get_user_id() else "他"}的信息"
            ),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await fit50.finish(msg, at_sender=True)
    elif not data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/maimai/-1.png")),
        )
        await fit50.finish(msg, at_sender=True)
    records = data["records"]
    if not records:
        await fit50.finish(
            (
                MessageSegment.text(
                    f"{"你" if target_qq == event.get_user_id() else "他"}没有上传任何成绩"
                ),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    songList = await get_music_data()
    b35, b15, mask_enabled = await records_to_bests(records, songList, is_fit=True)
    if not b35 and not b15:
        if mask_enabled:
            msg = f"迪拉熊无法获取{"你" if target_qq == event.get_user_id() else "他"}的真实成绩"
        else:
            msg = f"{"你" if target_qq == event.get_user_id() else "他"}没有上传任何匹配的成绩"
        await fit50.finish(
            (
                MessageSegment.text(msg),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    await fit50.send(MessageSegment.text("迪拉熊绘制中，稍等一下mai~"), at_sender=True)
    nickname = data["nickname"]
    dani = data["additional_rating"]
    with shelve.open("./data/user_config.db") as config:
        if target_qq not in config:
            frame = "200502"
            plate = "000101"
            is_rating_tj = True
        else:
            if "frame" not in config[target_qq]:
                frame = "200502"
            else:
                frame = config[target_qq]["frame"]
            if "plate" not in config[target_qq]:
                plate = "000101"
            else:
                plate = config[target_qq]["plate"]
            if "rating_tj" not in config[target_qq]:
                is_rating_tj = True
            else:
                is_rating_tj = config[target_qq]["rating_tj"]
    async with aiohttp.ClientSession(conn_timeout=3) as session:
        async with session.get(
            f"http://q.qlogo.cn/headimg_dl?dst_uin={target_qq}&spec=640&img_type=png"
        ) as resp:
            icon = await resp.read()
    start_time = time.perf_counter()
    img = await generatebests(
        b35=b35,
        b15=b15,
        nickname=nickname,
        dani=dani,
        type="fit50",
        icon=icon,
        frame=frame,
        plate=plate,
        is_rating_tj=is_rating_tj,
        songList=songList,
    )
    end_time = time.perf_counter()
    msg = (
        MessageSegment.image(img),
        MessageSegment.text(f"绘制用时：{end_time - start_time:.2f}秒"),
    )
    await fit50.send(msg, at_sender=True)


@best40.handle()
async def _(bot: Bot, event: MessageEvent):
    target_qq = event.get_user_id()
    for message in event.get_message():
        if message.type != "at":
            continue
        target_qq = message.data["qq"]
        if target_qq == event.get_user_id():
            continue
        if target_qq == bot.self_id:
            return
        with shelve.open("./data/user_config.db") as config:
            if (
                target_qq not in config
                or "allow_other" not in config[target_qq]
                or config[target_qq]["allow_other"]
            ):
                break
    else:
        if target_qq != event.get_user_id():
            msg = (
                MessageSegment.text("他不允许其他人查询他的成绩"),
                MessageSegment.image(Path("./Static/Maimai/Function/3.png")),
            )
            await best40.finish(msg, at_sender=True)
    data, status = await get_player_records(target_qq)
    if status == 400:
        msg = (
            MessageSegment.text(
                f"迪拉熊没有找到{"你" if target_qq == event.get_user_id() else "他"}的信息"
            ),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await best40.finish(msg, at_sender=True)
    elif not data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/maimai/-1.png")),
        )
        await best40.finish(msg, at_sender=True)
    records = data["records"]
    if not records:
        await best40.finish(
            (
                MessageSegment.text(
                    f"{"你" if target_qq == event.get_user_id() else "他"}没有上传任何成绩"
                ),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    songList = await get_music_data()
    b25, b15, _ = await records_to_bests(records, songList, is_old=True)
    await best40.send(MessageSegment.text("迪拉熊绘制中，稍等一下mai~"), at_sender=True)
    nickname = data["nickname"]
    dani = data["additional_rating"]
    with shelve.open("./data/user_config.db") as config:
        if target_qq not in config:
            frame = "200502"
            plate = "000101"
            is_rating_tj = True
        else:
            if "frame" not in config[target_qq]:
                frame = "200502"
            else:
                frame = config[target_qq]["frame"]
            if "plate" not in config[target_qq]:
                plate = "000101"
            else:
                plate = config[target_qq]["plate"]
            if "rating_tj" not in config[target_qq]:
                is_rating_tj = True
            else:
                is_rating_tj = config[target_qq]["rating_tj"]
    async with aiohttp.ClientSession(conn_timeout=3) as session:
        async with session.get(
            f"http://q.qlogo.cn/headimg_dl?dst_uin={target_qq}&spec=640&img_type=png"
        ) as resp:
            icon = await resp.read()
    start_time = time.perf_counter()
    img = await generatebests(
        b35=b25,
        b15=b15,
        nickname=nickname,
        dani=dani,
        type="best40",
        icon=icon,
        frame=frame,
        plate=plate,
        is_rating_tj=is_rating_tj,
        songList=songList,
    )
    end_time = time.perf_counter()
    msg = (
        MessageSegment.image(img),
        MessageSegment.text(f"绘制用时：{end_time - start_time:.2f}秒"),
    )
    await best40.send(msg, at_sender=True)


@rate50.handle()
async def _(bot: Bot, event: MessageEvent):
    target_qq = event.get_user_id()
    for message in event.get_message():
        if message.type != "at":
            continue
        target_qq = message.data["qq"]
        if target_qq == event.get_user_id():
            continue
        if target_qq == bot.self_id:
            return
        with shelve.open("./data/user_config.db") as config:
            if (
                target_qq not in config
                or "allow_other" not in config[target_qq]
                or config[target_qq]["allow_other"]
            ):
                break
    else:
        if target_qq != event.get_user_id():
            msg = (
                MessageSegment.text("他不允许其他人查询他的成绩"),
                MessageSegment.image(Path("./Static/Maimai/Function/3.png")),
            )
            await rate50.finish(msg, at_sender=True)
    data, status = await get_player_records(target_qq)
    if status == 400:
        msg = (
            MessageSegment.text(
                f"迪拉熊没有找到{"你" if target_qq == event.get_user_id() else "他"}的信息"
            ),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await rate50.finish(msg, at_sender=True)
    elif not data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/maimai/-1.png")),
        )
        await rate50.finish(msg, at_sender=True)
    records = data["records"]
    if not records:
        await rate50.finish(
            (
                MessageSegment.text(
                    f"{"你" if target_qq == event.get_user_id() else "他"}没有上传任何成绩"
                ),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    msg_text = event.get_plaintext().replace("+", "p").casefold()
    rate_rules = re.findall(r"s{1,3}p?|a{1,3}|b{1,3}|[cd]", msg_text, re.I)
    songList = await get_music_data()
    rate35, rate15, _ = await records_to_bests(records, songList, rate_rules=rate_rules)
    if not rate35 and not rate15:
        await rate50.finish(
            (
                MessageSegment.text(
                    f"{"你" if target_qq == event.get_user_id() else "他"}没有上传任何匹配的成绩"
                ),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    await rate50.send(MessageSegment.text("迪拉熊绘制中，稍等一下mai~"), at_sender=True)
    nickname = data["nickname"]
    dani = data["additional_rating"]
    with shelve.open("./data/user_config.db") as config:
        if target_qq not in config:
            frame = "200502"
            plate = "000101"
            is_rating_tj = True
        else:
            if "frame" not in config[target_qq]:
                frame = "200502"
            else:
                frame = config[target_qq]["frame"]
            if "plate" not in config[target_qq]:
                plate = "000101"
            else:
                plate = config[target_qq]["plate"]
            if "rating_tj" not in config[target_qq]:
                is_rating_tj = True
            else:
                is_rating_tj = config[target_qq]["rating_tj"]
    async with aiohttp.ClientSession(conn_timeout=3) as session:
        async with session.get(
            f"http://q.qlogo.cn/headimg_dl?dst_uin={target_qq}&spec=640&img_type=png"
        ) as resp:
            icon = await resp.read()
    start_time = time.perf_counter()
    img = await generatebests(
        b35=rate35,
        b15=rate15,
        nickname=nickname,
        dani=dani,
        type="rate50",
        icon=icon,
        frame=frame,
        plate=plate,
        is_rating_tj=is_rating_tj,
        songList=songList,
    )
    end_time = time.perf_counter()
    msg = (
        MessageSegment.image(img),
        MessageSegment.text(f"绘制用时：{end_time - start_time:.2f}秒"),
    )
    await rate50.send(msg, at_sender=True)


@dxs50.handle()
async def _(bot: Bot, event: MessageEvent):
    target_qq = event.get_user_id()
    for message in event.get_message():
        if message.type != "at":
            continue
        target_qq = message.data["qq"]
        if target_qq == event.get_user_id():
            continue
        if target_qq == bot.self_id:
            return
        with shelve.open("./data/user_config.db") as config:
            if (
                target_qq not in config
                or "allow_other" not in config[target_qq]
                or config[target_qq]["allow_other"]
            ):
                break
    else:
        if target_qq != event.get_user_id():
            msg = (
                MessageSegment.text("他不允许其他人查询他的成绩"),
                MessageSegment.image(Path("./Static/Maimai/Function/3.png")),
            )
            await dxs50.finish(msg, at_sender=True)
    data, status = await get_player_records(target_qq)
    if status == 400:
        msg = (
            MessageSegment.text(
                f"迪拉熊没有找到{"你" if target_qq == event.get_user_id() else "他"}的信息"
            ),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await dxs50.finish(msg, at_sender=True)
    elif not data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/maimai/-1.png")),
        )
        await dxs50.finish(msg, at_sender=True)
    records = data["records"]
    if not records:
        await dxs50.finish(
            (
                MessageSegment.text(
                    f"{"你" if target_qq == event.get_user_id() else "他"}没有上传任何成绩"
                ),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    songList = await get_music_data()
    dxs35, dxs15, mask_enabled = await records_to_bests(records, songList, is_dxs=True)
    if not dxs35 and not dxs15:
        if mask_enabled:
            msg = f"迪拉熊无法获取{"你" if target_qq == event.get_user_id() else "他"}的真实成绩"
        else:
            msg = f"{"你" if target_qq == event.get_user_id() else "他"}没有上传任何匹配的成绩"
        await dxs50.finish(
            (
                MessageSegment.text(msg),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    await dxs50.send(MessageSegment.text("迪拉熊绘制中，稍等一下mai~"), at_sender=True)
    nickname = data["nickname"]
    dani = data["additional_rating"]
    with shelve.open("./data/user_config.db") as config:
        if target_qq not in config:
            frame = "200502"
            plate = "000101"
            is_rating_tj = True
        else:
            if "frame" not in config[target_qq]:
                frame = "200502"
            else:
                frame = config[target_qq]["frame"]
            if "plate" not in config[target_qq]:
                plate = "000101"
            else:
                plate = config[target_qq]["plate"]
            if "rating_tj" not in config[target_qq]:
                is_rating_tj = True
            else:
                is_rating_tj = config[target_qq]["rating_tj"]
    async with aiohttp.ClientSession(conn_timeout=3) as session:
        async with session.get(
            f"http://q.qlogo.cn/headimg_dl?dst_uin={target_qq}&spec=640&img_type=png"
        ) as resp:
            icon = await resp.read()
    start_time = time.perf_counter()
    img = await generatebests(
        b35=dxs35,
        b15=dxs15,
        nickname=nickname,
        dani=dani,
        type="dxs50",
        icon=icon,
        frame=frame,
        plate=plate,
        is_rating_tj=is_rating_tj,
        songList=songList,
    )
    end_time = time.perf_counter()
    msg = (
        MessageSegment.image(img),
        MessageSegment.text(f"绘制用时：{end_time - start_time:.2f}秒"),
    )
    await dxs50.send(msg, at_sender=True)


@star50.handle()
async def _(bot: Bot, event: MessageEvent):
    target_qq = event.get_user_id()
    for message in event.get_message():
        if message.type != "at":
            continue
        target_qq = message.data["qq"]
        if target_qq == event.get_user_id():
            continue
        if target_qq == bot.self_id:
            return
        with shelve.open("./data/user_config.db") as config:
            if (
                target_qq not in config
                or "allow_other" not in config[target_qq]
                or config[target_qq]["allow_other"]
            ):
                break
    else:
        if target_qq != event.get_user_id():
            msg = (
                MessageSegment.text("他不允许其他人查询他的成绩"),
                MessageSegment.image(Path("./Static/Maimai/Function/3.png")),
            )
            await star50.finish(msg, at_sender=True)
    data, status = await get_player_records(target_qq)
    if status == 400:
        msg = (
            MessageSegment.text(
                f"迪拉熊没有找到{"你" if target_qq == event.get_user_id() else "他"}的信息"
            ),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await star50.finish(msg, at_sender=True)
    elif not data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/maimai/-1.png")),
        )
        await star50.finish(msg, at_sender=True)
    records = data["records"]
    if not records:
        await star50.finish(
            (
                MessageSegment.text(
                    f"{"你" if target_qq == event.get_user_id() else "他"}没有上传任何成绩"
                ),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    songList = await get_music_data()
    find = re.fullmatch(r"dlxx50((?:\s*[1-5])+)", event.get_plaintext(), re.I)
    star35, star15, mask_enabled = await records_to_bests(
        records, songList, is_dxs=True, dx_star_count=find.group(1)
    )
    if not star35 and not star15:
        if mask_enabled:
            msg = f"迪拉熊无法获取{"你" if target_qq == event.get_user_id() else "他"}的真实成绩"
        else:
            msg = f"{"你" if target_qq == event.get_user_id() else "他"}没有上传任何匹配的成绩"
        await star50.finish(
            (
                MessageSegment.text(msg),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    await star50.send(MessageSegment.text("迪拉熊绘制中，稍等一下mai~"), at_sender=True)
    nickname = data["nickname"]
    dani = data["additional_rating"]
    with shelve.open("./data/user_config.db") as config:
        if target_qq not in config:
            frame = "200502"
            plate = "000101"
            is_rating_tj = True
        else:
            if "frame" not in config[target_qq]:
                frame = "200502"
            else:
                frame = config[target_qq]["frame"]
            if "plate" not in config[target_qq]:
                plate = "000101"
            else:
                plate = config[target_qq]["plate"]
            if "rating_tj" not in config[target_qq]:
                is_rating_tj = True
            else:
                is_rating_tj = config[target_qq]["rating_tj"]
    async with aiohttp.ClientSession(conn_timeout=3) as session:
        async with session.get(
            f"http://q.qlogo.cn/headimg_dl?dst_uin={target_qq}&spec=640&img_type=png"
        ) as resp:
            icon = await resp.read()
    start_time = time.perf_counter()
    img = await generatebests(
        b35=star35,
        b15=star15,
        nickname=nickname,
        dani=dani,
        type="star50",
        icon=icon,
        frame=frame,
        plate=plate,
        is_rating_tj=is_rating_tj,
        songList=songList,
    )
    end_time = time.perf_counter()
    msg = (
        MessageSegment.image(img),
        MessageSegment.text(f"绘制用时：{end_time - start_time:.2f}秒"),
    )
    await star50.send(msg, at_sender=True)


@cf50.handle()
async def _(bot: Bot, event: MessageEvent):
    sender_qq = event.get_user_id()
    target_qq = None
    for message in event.get_message():
        if message.type != "at":
            continue
        target_qq = message.data["qq"]
        if target_qq == sender_qq:
            continue
        if target_qq == bot.self_id:
            return
        with shelve.open("./data/user_config.db") as config:
            if (
                target_qq not in config
                or "allow_other" not in config[target_qq]
                or config[target_qq]["allow_other"]
            ):
                break
    else:
        if target_qq != sender_qq:
            msg = (
                MessageSegment.text("他不允许其他人查询他的成绩"),
                MessageSegment.image(Path("./Static/Maimai/Function/3.png")),
            )
            await cf50.finish(msg, at_sender=True)
    if target_qq == None:
        msg = (
            MessageSegment.text("你没有比较任何人"),
            MessageSegment.image(Path("./Static/Maimai/Function/3.png")),
        )
        await cf50.finish(msg, at_sender=True)
    if target_qq == sender_qq:
        msg = (
            MessageSegment.text("你不可以和自己比较"),
            MessageSegment.image(Path("./Static/Maimai/Function/3.png")),
        )
        await cf50.finish(msg, at_sender=True)
    sender_data, status = await get_player_records(sender_qq)
    if status == 400:
        msg = (
            MessageSegment.text("迪拉熊没有找到你的信息"),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await cf50.finish(msg, at_sender=True)
    elif status == 403:
        msg = (
            MessageSegment.text("你在查分器启用了隐私或者没有同意查分器的用户协议"),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await cf50.finish(msg, at_sender=True)
    elif not sender_data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/maimai/-1.png")),
        )
        await cf50.finish(msg, at_sender=True)
    target_data, status = await get_player_records(target_qq)
    if status == 400:
        msg = (
            MessageSegment.text("迪拉熊没有找到他的信息"),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await cf50.finish(msg, at_sender=True)
    elif status == 403:
        msg = (
            MessageSegment.text("他在查分器启用了隐私或者没有同意查分器的用户协议"),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await cf50.finish(msg, at_sender=True)
    elif not target_data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/maimai/-1.png")),
        )
        await cf50.finish(msg, at_sender=True)
    songList = await get_music_data()
    sender_records = sender_data["records"]
    if not sender_records:
        await cf50.finish(
            (
                MessageSegment.text("你没有上传任何成绩"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    target_records = target_data["records"]
    if not target_records:
        await cf50.finish(
            (
                MessageSegment.text("他没有上传任何成绩"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    songList = await get_music_data()
    b35, b15, mask_enabled = await compare_bests(
        sender_records, target_records, songList
    )
    if not b35 and not b15:
        if mask_enabled:
            msg = "迪拉熊无法获取真实成绩"
        else:
            msg = "没有上传任何匹配的成绩"
        await cf50.finish(
            (
                MessageSegment.text(msg),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    await cf50.send(MessageSegment.text("迪拉熊绘制中，稍等一下mai~"), at_sender=True)
    nickname = target_data["nickname"]
    dani = target_data["additional_rating"]
    with shelve.open("./data/user_config.db") as config:
        if target_qq not in config:
            frame = "200502"
            plate = "000101"
            is_rating_tj = True
        else:
            if "frame" not in config[target_qq]:
                frame = "200502"
            else:
                frame = config[target_qq]["frame"]
            if "plate" not in config[target_qq]:
                plate = "000101"
            else:
                plate = config[target_qq]["plate"]
            if "rating_tj" not in config[target_qq]:
                is_rating_tj = True
            else:
                is_rating_tj = config[target_qq]["rating_tj"]
    async with aiohttp.ClientSession(conn_timeout=3) as session:
        async with session.get(
            f"http://q.qlogo.cn/headimg_dl?dst_uin={target_qq}&spec=640&img_type=png"
        ) as resp:
            icon = await resp.read()
    start_time = time.perf_counter()
    img = await generatebests(
        b35=b35,
        b15=b15,
        nickname=nickname,
        dani=dani,
        type="cf50",
        icon=icon,
        frame=frame,
        plate=plate,
        is_rating_tj=is_rating_tj,
        songList=songList,
    )
    end_time = time.perf_counter()
    msg = (
        MessageSegment.image(img),
        MessageSegment.text(f"绘制用时：{end_time - start_time:.2f}秒"),
    )
    await cf50.send(msg, at_sender=True)


@sd50.handle()
async def _(bot: Bot, event: MessageEvent):
    target_qq = event.get_user_id()
    for message in event.get_message():
        if message.type != "at":
            continue
        target_qq = message.data["qq"]
        if target_qq == event.get_user_id():
            continue
        if target_qq == bot.self_id:
            return
        with shelve.open("./data/user_config.db") as config:
            if (
                target_qq not in config
                or "allow_other" not in config[target_qq]
                or config[target_qq]["allow_other"]
            ):
                break
    else:
        if target_qq != event.get_user_id():
            msg = (
                MessageSegment.text("他不允许其他人查询他的成绩"),
                MessageSegment.image(Path("./Static/Maimai/Function/3.png")),
            )
            await sd50.finish(msg, at_sender=True)
    data, status = await get_player_records(target_qq)
    if status == 400:
        msg = (
            MessageSegment.text(
                f"迪拉熊没有找到{"你" if target_qq == event.get_user_id() else "他"}的信息"
            ),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await sd50.finish(msg, at_sender=True)
    elif not data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/maimai/-1.png")),
        )
        await sd50.finish(msg, at_sender=True)
    records = data["records"]
    if not records:
        await sd50.finish(
            (
                MessageSegment.text(
                    f"{"你" if target_qq == event.get_user_id() else "他"}没有上传任何成绩"
                ),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    songList = await get_music_data()
    b35, b15, mask_enabled = await records_to_bests(records, songList, is_sd=True)
    if not b35 and not b15:
        if mask_enabled:
            msg = f"迪拉熊无法获取{"你" if target_qq == event.get_user_id() else "他"}的真实成绩"
        else:
            msg = f"{"你" if target_qq == event.get_user_id() else "他"}没有上传任何匹配的成绩"
        await sd50.finish(
            (
                MessageSegment.text(msg),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    await sd50.send(MessageSegment.text("迪拉熊绘制中，稍等一下mai~"), at_sender=True)
    nickname = data["nickname"]
    dani = data["additional_rating"]
    with shelve.open("./data/user_config.db") as config:
        if target_qq not in config:
            frame = "200502"
            plate = "000101"
            is_rating_tj = True
        else:
            if "frame" not in config[target_qq]:
                frame = "200502"
            else:
                frame = config[target_qq]["frame"]
            if "plate" not in config[target_qq]:
                plate = "000101"
            else:
                plate = config[target_qq]["plate"]
            if "rating_tj" not in config[target_qq]:
                is_rating_tj = True
            else:
                is_rating_tj = config[target_qq]["rating_tj"]
    async with aiohttp.ClientSession(conn_timeout=3) as session:
        async with session.get(
            f"http://q.qlogo.cn/headimg_dl?dst_uin={target_qq}&spec=640&img_type=png"
        ) as resp:
            icon = await resp.read()
    start_time = time.perf_counter()
    img = await generatebests(
        b35=b35,
        b15=b15,
        nickname=nickname,
        dani=dani,
        type="sd50",
        icon=icon,
        frame=frame,
        plate=plate,
        is_rating_tj=is_rating_tj,
        songList=songList,
    )
    end_time = time.perf_counter()
    msg = (
        MessageSegment.image(img),
        MessageSegment.text(f"绘制用时：{end_time - start_time:.2f}秒"),
    )
    await sd50.send(msg, at_sender=True)


@all50.handle()
async def _(bot: Bot, event: MessageEvent):
    target_qq = event.get_user_id()
    for message in event.get_message():
        if message.type != "at":
            continue
        target_qq = message.data["qq"]
        if target_qq == event.get_user_id():
            continue
        if target_qq == bot.self_id:
            return
        with shelve.open("./data/user_config.db") as config:
            if (
                target_qq not in config
                or "allow_other" not in config[target_qq]
                or config[target_qq]["allow_other"]
            ):
                break
    else:
        if target_qq != event.get_user_id():
            msg = (
                MessageSegment.text("他不允许其他人查询他的成绩"),
                MessageSegment.image(Path("./Static/Maimai/Function/3.png")),
            )
            await all50.finish(msg, at_sender=True)
    data, status = await get_player_records(target_qq)
    if status == 400:
        msg = (
            MessageSegment.text(
                f"迪拉熊没有找到{"你" if target_qq == event.get_user_id() else "他"}的信息"
            ),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await all50.finish(msg, at_sender=True)
    elif not data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/maimai/-1.png")),
        )
        await all50.finish(msg, at_sender=True)
    records = data["records"]
    if not records:
        await all50.finish(
            (
                MessageSegment.text(
                    f"{"你" if target_qq == event.get_user_id() else "他"}没有上传任何成绩"
                ),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    songList = await get_music_data()
    all35, all15, _ = await records_to_bests(records, songList, is_all=True)
    await all50.send(MessageSegment.text("迪拉熊绘制中，稍等一下mai~"), at_sender=True)
    nickname = data["nickname"]
    dani = data["additional_rating"]
    with shelve.open("./data/user_config.db") as config:
        if target_qq not in config:
            frame = "200502"
            plate = "000101"
            is_rating_tj = True
        else:
            if "frame" not in config[target_qq]:
                frame = "200502"
            else:
                frame = config[target_qq]["frame"]
            if "plate" not in config[target_qq]:
                plate = "000101"
            else:
                plate = config[target_qq]["plate"]
            if "rating_tj" not in config[target_qq]:
                is_rating_tj = True
            else:
                is_rating_tj = config[target_qq]["rating_tj"]
    async with aiohttp.ClientSession(conn_timeout=3) as session:
        async with session.get(
            f"http://q.qlogo.cn/headimg_dl?dst_uin={target_qq}&spec=640&img_type=png"
        ) as resp:
            icon = await resp.read()
    start_time = time.perf_counter()
    img = await generatebests(
        b35=all35,
        b15=all15,
        nickname=nickname,
        dani=dani,
        type="all50",
        icon=icon,
        frame=frame,
        plate=plate,
        is_rating_tj=is_rating_tj,
        songList=songList,
    )
    end_time = time.perf_counter()
    msg = (
        MessageSegment.image(img),
        MessageSegment.text(f"绘制用时：{end_time - start_time:.2f}秒"),
    )
    await all50.send(msg, at_sender=True)


@rr50.handle()
async def _(event: MessageEvent):
    match = re.fullmatch(r"dlxrr(?:50)?\s*(\d+)", event.get_plaintext(), re.I)
    rating = 0
    if match:
        rating = int(match.group(1))
        if rating < 0:
            await rr50.send(
                (
                    MessageSegment.text("没有任何匹配的成绩"),
                    MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
                ),
                at_sender=True,
            )
            return

    songList = await get_music_data()
    rr35, rr15, _ = await records_to_bests(
        None,
        songList,
        rating=rating,
    )
    if not rr35 and not rr15:
        await rr50.send(
            (
                MessageSegment.text("没有任何匹配的成绩"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
        return

    await rr50.send(MessageSegment.text("迪拉熊绘制中，稍等一下mai~"), at_sender=True)
    async with aiohttp.ClientSession(conn_timeout=3) as session:
        async with session.get(
            "http://q.qlogo.cn/headimg_dl?dst_uin=0&spec=640&img_type=png"
        ) as resp:
            icon = await resp.read()
    nickname = "ｍａｉｍａｉ"
    dani = 22
    start_time = time.perf_counter()
    img = await generatebests(
        b35=rr35,
        b15=rr15,
        nickname=nickname,
        dani=dani,
        type="rr50",
        icon=icon,
        frame="200502",
        plate="000101",
        is_rating_tj=False,
        songList=songList,
    )
    end_time = time.perf_counter()
    msg = (
        MessageSegment.image(img),
        MessageSegment.text(f"绘制用时：{end_time - start_time:.2f}秒"),
    )
    await rr50.send(msg, at_sender=True)


@sunlist.handle()
async def _(event: MessageEvent):
    qq = event.get_user_id()
    data, status = await get_player_records(qq)
    if status == 400:
        msg = (
            MessageSegment.text("迪拉熊没有找到你的信息"),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await sunlist.finish(msg, at_sender=True)
    elif not data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/maimai/-1.png")),
        )
        await sunlist.finish(msg, at_sender=True)
    records = data["records"]
    if not records:
        await sunlist.finish(
            (
                MessageSegment.text("你没有上传任何成绩"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    songList = await get_music_data()
    filted_records, mask_enabled = records_filter(
        records=records, is_sun=True, songList=songList
    )
    if not filted_records:
        if mask_enabled:
            msg = "迪拉熊无法获取你的真实成绩"
        else:
            msg = "你没有上传任何匹配的成绩"
        await sunlist.finish(
            (
                MessageSegment.text(msg),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    msg = event.get_plaintext()
    pattern = r"\d+"
    match = re.search(pattern, msg)
    if match:
        page = int(match.group())
        if page <= 0:
            page = 1
    else:
        page = 1
    all_page_num = math.ceil(len(filted_records) / 55)
    page = min(page, all_page_num)
    await sunlist.send(
        MessageSegment.text("迪拉熊绘制中，稍等一下mai~"), at_sender=True
    )
    input_records = get_page_records(filted_records, page=page)
    nickname = data["nickname"]
    rating = data["rating"]
    dani = data["additional_rating"]
    with shelve.open("./data/user_config.db") as config:
        if qq not in config or "plate" not in config[qq]:
            plate = "000101"
        else:
            plate = config[qq]["plate"]
        if qq not in config or "frame" not in config[qq]:
            frame = "200502"
        else:
            frame = config[qq]["frame"]
    async with aiohttp.ClientSession(conn_timeout=3) as session:
        async with session.get(
            f"http://q.qlogo.cn/headimg_dl?dst_uin={qq}&spec=640&img_type=png"
        ) as resp:
            icon = await resp.read()
    start_time = time.perf_counter()
    img = await generate_wcb(
        page=page,
        nickname=nickname,
        dani=dani,
        rating=rating,
        icon=icon,
        frame=frame,
        plate=plate,
        input_records=input_records,
        all_page_num=all_page_num,
        songList=songList,
    )
    end_time = time.perf_counter()
    msg = (
        MessageSegment.image(img),
        MessageSegment.text(f"绘制用时：{end_time - start_time:.2f}秒"),
    )
    await sunlist.send(msg, at_sender=True)


@locklist.handle()
async def _(event: MessageEvent):
    qq = event.get_user_id()
    data, status = await get_player_records(qq)
    if status == 400:
        msg = (
            MessageSegment.text("迪拉熊没有找到你的信息"),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await locklist.finish(msg, at_sender=True)
    elif not data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/maimai/-1.png")),
        )
        await locklist.finish(msg, at_sender=True)
    records = data["records"]
    if not records:
        await locklist.finish(
            (
                MessageSegment.text("你没有上传任何成绩"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    songList = await get_music_data()
    filted_records, mask_enabled = records_filter(
        records=records, is_lock=True, songList=songList
    )
    if not filted_records:
        if mask_enabled:
            msg = "迪拉熊无法获取你的真实成绩"
        else:
            msg = "你没有上传任何匹配的成绩"
        await locklist.finish(
            (
                MessageSegment.text(msg),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    msg = event.get_plaintext()
    pattern = r"\d+"
    match = re.search(pattern, msg)
    if match:
        page = int(match.group())
        if page <= 0:
            page = 1
    else:
        page = 1
    all_page_num = math.ceil(len(filted_records) / 55)
    page = min(page, all_page_num)
    await locklist.send(
        MessageSegment.text("迪拉熊绘制中，稍等一下mai~"), at_sender=True
    )
    input_records = get_page_records(filted_records, page=page)
    nickname = data["nickname"]
    rating = data["rating"]
    dani = data["additional_rating"]
    with shelve.open("./data/user_config.db") as config:
        if qq not in config or "plate" not in config[qq]:
            plate = "000101"
        else:
            plate = config[qq]["plate"]
        if qq not in config or "frame" not in config[qq]:
            frame = "200502"
        else:
            frame = config[qq]["frame"]
    async with aiohttp.ClientSession(conn_timeout=3) as session:
        async with session.get(
            f"http://q.qlogo.cn/headimg_dl?dst_uin={qq}&spec=640&img_type=png"
        ) as resp:
            icon = await resp.read()
    start_time = time.perf_counter()
    img = await generate_wcb(
        page=page,
        nickname=nickname,
        dani=dani,
        rating=rating,
        icon=icon,
        frame=frame,
        plate=plate,
        input_records=input_records,
        all_page_num=all_page_num,
        songList=songList,
    )
    end_time = time.perf_counter()
    msg = (
        MessageSegment.image(img),
        MessageSegment.text(f"绘制用时：{end_time - start_time:.2f}秒"),
    )
    await locklist.send(msg, at_sender=True)


@wcb.handle()
async def _(event: MessageEvent):
    qq = event.get_user_id()
    msg = event.get_plaintext()
    pattern = r"(?:((?:\d+)(?:\.\d|\+)?)|(真|超|檄|橙|晓|桃|樱|紫|堇|白|雪|辉|舞|熊|华|爽|煌|宙|星|祭|祝|双))(?:\s*(\d+))?"
    match = re.search(pattern, msg)
    data, status = await get_player_records(qq)
    if status == 400:
        msg = (
            MessageSegment.text("迪拉熊没有找到你的信息"),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await wcb.finish(msg, at_sender=True)
    elif not data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/maimai/-1.png")),
        )
        await wcb.finish(msg, at_sender=True)
    records = data["records"]
    if not records:
        await wcb.finish(
            (
                MessageSegment.text("你没有上传任何成绩"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    songList = await get_music_data()
    level = match.group(1)
    if level and "." in level:
        ds = float(level)
        level = None
    else:
        ds = None
    gen = match.group(2)
    filted_records, _ = records_filter(
        records=records, level=level, ds=ds, gen=gen, songList=songList
    )
    if len(filted_records) == 0:
        await wcb.finish(
            (
                MessageSegment.text("你没有上传任何匹配的成绩"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )

    if match.group(3):
        page = int(match.group(3))
        if page <= 0:
            page = 1
    else:
        page = 1
    all_page_num = math.ceil(len(filted_records) / 55)
    page = min(page, all_page_num)
    await wcb.send(MessageSegment.text("迪拉熊绘制中，稍等一下mai~"), at_sender=True)
    input_records = get_page_records(filted_records, page=page)
    rate_count = compute_record(records=filted_records)
    nickname = data["nickname"]
    rating = data["rating"]
    dani = data["additional_rating"]
    with shelve.open("./data/user_config.db") as config:
        if qq not in config or "plate" not in config[qq]:
            plate = "000101"
        else:
            plate = config[qq]["plate"]
        if qq not in config or "frame" not in config[qq]:
            frame = "200502"
        else:
            frame = config[qq]["frame"]
    async with aiohttp.ClientSession(conn_timeout=3) as session:
        async with session.get(
            f"http://q.qlogo.cn/headimg_dl?dst_uin={qq}&spec=640&img_type=png"
        ) as resp:
            icon = await resp.read()
    start_time = time.perf_counter()
    img = await generate_wcb(
        level=level,
        ds=ds,
        gen=gen,
        page=page,
        nickname=nickname,
        dani=dani,
        rating=rating,
        icon=icon,
        frame=frame,
        plate=plate,
        input_records=input_records,
        rate_count=rate_count,
        all_page_num=all_page_num,
        songList=songList,
    )
    end_time = time.perf_counter()
    msg = (
        MessageSegment.image(img),
        MessageSegment.text(f"绘制用时：{end_time - start_time:.2f}秒"),
    )
    await wcb.send(msg, at_sender=True)


@songinfo.handle()
async def _(event: MessageEvent):
    msg = event.get_plaintext()
    match = re.fullmatch(r"(?:chart|id)\s*(?:(dx|sd|标准?)\s*)?(.+)", msg, re.I)
    if not match:
        return

    music_type = match.group(1)
    song = match.group(2)
    if not song:
        return

    songList = await get_music_data()
    result, song_info = await get_info_by_name(song, music_type, songList)
    if result == 1:
        if isinstance(song_info, set):
            msg = f"迪拉熊找到啦~结果有：\r\n{"\r\n".join(song_info)}"
            await songinfo.finish(MessageSegment.text(msg))
    elif result == 2:
        await songinfo.finish(
            (
                MessageSegment.text("迪拉熊没有找到匹配的乐曲"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    elif result == 3:
        await songinfo.finish(
            (
                MessageSegment.text("结果太多啦，缩小范围再试试吧~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    await songinfo.send(
        MessageSegment.text("迪拉熊绘制中，稍等一下mai~"), at_sender=True
    )
    if song_info["basic_info"]["genre"] == "宴会場":
        start_time = time.perf_counter()
        img = await utage_music_info(song_data=song_info)
    else:
        start_time = time.perf_counter()
        img = await music_info(song_data=song_info)
    end_time = time.perf_counter()
    msg = (
        MessageSegment.image(img),
        MessageSegment.text(f"绘制用时：{end_time - start_time:.2f}秒"),
    )
    await songinfo.send(msg)


@playinfo.handle()
async def _(event: MessageEvent):
    qq = event.get_user_id()
    msg = event.get_plaintext()
    match = re.fullmatch(r"(?:score|info)\s*(?:(dx|sd|标准?)\s*)?(.+)", msg, re.I)
    if not match:
        return

    music_type = match.group(1)
    song = match.group(2)
    if not song:
        return

    songList = await get_music_data()
    result, song_info = await get_info_by_name(song, music_type, songList)
    if result == 1:
        if isinstance(song_info, set):
            msg = f"迪拉熊找到啦~结果有：\r\n{"\r\n".join(song_info)}"
            await playinfo.finish(MessageSegment.text(msg))
    elif result == 2:
        await playinfo.finish(
            (
                MessageSegment.text("迪拉熊没有找到匹配的乐曲"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    elif result == 3:
        await playinfo.finish(
            (
                MessageSegment.text("结果太多啦，缩小范围再试试吧~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    data, status = await get_player_record(qq, song_info["id"])
    if status == 400:
        msg = (
            MessageSegment.text("迪拉熊没有找到你的信息"),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await playinfo.finish(msg, at_sender=True)
    if status == 200:
        if not data:
            msg = (
                MessageSegment.text("迪拉熊没有找到匹配的乐曲"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            )
            await playinfo.finish(msg, at_sender=True)
        records = data[song_info["id"]]
        if not records:
            msg = (
                MessageSegment.text("迪拉熊没有找到你在这首乐曲上的成绩"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            )
            await playinfo.finish(msg, at_sender=True)
    elif not data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/maimai/-1.png")),
        )
        await playinfo.finish(msg, at_sender=True)
    await playinfo.send(
        MessageSegment.text("迪拉熊绘制中，稍等一下mai~"), at_sender=True
    )
    start_time = time.perf_counter()
    img = await play_info(data, song_info)
    end_time = time.perf_counter()
    msg = (
        MessageSegment.image(img),
        MessageSegment.text(f"绘制用时：{end_time - start_time:.2f}秒"),
    )
    await playinfo.send(msg, at_sender=True)


@scoreinfo.handle()
async def _(event: MessageEvent):
    msg = event.get_plaintext()
    pattern = r"(绿|黄|红|紫|白)\s*(?:(dx|sd|标准?)\s*)?(.+)"
    match = re.search(pattern, msg, re.I)
    type_index = ["绿", "黄", "红", "紫", "白"].index(match.group(1))
    music_type = match.group(2)
    song = match.group(3)
    if not song:
        return

    songList = await get_music_data()
    result, song_info = await get_info_by_name(song, music_type, songList)
    if result == 1:
        if isinstance(song_info, set):
            msg = f"迪拉熊找到啦~结果有：\r\n{"\r\n".join(song_info)}"
            await scoreinfo.finish(MessageSegment.text(msg))
    elif (
        result == 2
        or song_info["basic_info"]["genre"] == "宴会場"
        or len(song_info["level"]) <= type_index
    ):
        await scoreinfo.finish(
            (
                MessageSegment.text("迪拉熊没有找到匹配的乐曲"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    elif result == 3:
        await scoreinfo.finish(
            (
                MessageSegment.text("结果太多啦，缩小范围再试试吧~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    await scoreinfo.send(
        MessageSegment.text("迪拉熊绘制中，稍等一下mai~"), at_sender=True
    )
    start_time = time.perf_counter()
    img = await score_info(song_data=song_info, index=type_index)
    end_time = time.perf_counter()
    msg = (
        MessageSegment.image(img),
        MessageSegment.text(f"绘制用时：{end_time - start_time:.2f}秒"),
    )
    await scoreinfo.send(msg)


@playaudio.handle()
async def _(event: MessageEvent):
    msg = event.get_plaintext()
    match = re.fullmatch(r"dlx点歌\s*(.+)", msg, re.I)
    if not match:
        return

    song = match.group(1)
    if not song:
        return

    songList = await get_music_data()
    result, song_info = await get_info_by_name(song, None, songList)
    if result == 1:
        if isinstance(song_info, set):
            msg = f"迪拉熊找到啦~结果有：\r\n{"\r\n".join(song_info)}"
            await playaudio.finish(MessageSegment.text(msg))
    elif result == 2:
        await playaudio.finish(
            (
                MessageSegment.text("迪拉熊没有找到匹配的乐曲"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    elif result == 3:
        await playaudio.finish(
            (
                MessageSegment.text("结果太多啦，缩小范围再试试吧~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )

    song_id = int(song_info["id"]) % 10000
    await playaudio.send(
        MessageSegment.music_custom(
            url=f"https://maimai.lxns.net/songs?game=maimai&song_id={song_id}",
            audio=f"https://assets2.lxns.net/maimai/music/{song_id}.mp3",
            title=song_info["title"],
            content=song_info["basic_info"]["artist"],
            img_url=f"https://assets2.lxns.net/maimai/jacket/{song_id}.png",
        )
    )


@randomsong.handle()
async def _(event: MessageEvent):
    rng = random.default_rng()
    msg = event.get_plaintext()
    pattern = r"(绿|黄|红|紫|白)?\s*((?:\d+)(?:\.\d|\+)?)"
    match = re.search(pattern, msg)
    level_label = match.group(1)
    if level_label:
        level_index = ["绿", "黄", "红", "紫", "白"].index(level_label)
    else:
        level_index = None
    level = match.group(2)
    s_type = "level"
    if "." in level:
        s_type = "ds"
    s_songs = list()
    songList = await get_music_data()
    for song in songList:
        if song["basic_info"]["genre"] == "宴会場":
            continue
        s_list = song[s_type]
        if s_type == "ds":
            level = float(level)
        if level_index:
            if len(s_list) > level_index:
                if level == s_list[level_index]:
                    s_songs.append(song)
        elif level in s_list:
            s_songs.append(song)
    if len(s_songs) == 0:
        msg = "迪拉熊没有找到匹配的乐曲"
        await randomsong.finish(MessageSegment.text(msg), at_sender=True)
    song = rng.choice(s_songs)
    await randomsong.send(
        MessageSegment.text("迪拉熊绘制中，稍等一下mai~"), at_sender=True
    )
    start_time = time.perf_counter()
    img = await music_info(song_data=song)
    end_time = time.perf_counter()
    msg = (
        MessageSegment.image(img),
        MessageSegment.text(f"绘制用时：{end_time - start_time:.2f}秒"),
    )
    await randomsong.send(msg, at_sender=True)


@maiwhat.handle()
async def _(event: MessageEvent):
    rng = random.default_rng()
    songList = await get_music_data()
    song = rng.choice(songList)
    await maiwhat.send(
        MessageSegment.text("迪拉熊绘制中，稍等一下mai~"), at_sender=True
    )
    if song["basic_info"]["genre"] == "宴会場":
        start_time = time.perf_counter()
        img = await utage_music_info(song_data=song)
    else:
        start_time = time.perf_counter()
        img = await music_info(song_data=song)
    end_time = time.perf_counter()
    msg = (
        MessageSegment.image(img),
        MessageSegment.text(f"绘制用时：{end_time - start_time:.2f}秒"),
    )
    await maiwhat.send(msg, at_sender=True)


@whatSong.handle()
async def _(event: MessageEvent):
    msg = event.get_plaintext()
    match = re.fullmatch(
        r"(?:search|查歌)\s*(?:(dx|sd|标准?)\s*)?(.+)|(?:(dx|sd|标准?)\s*)?(.+)是什么歌？?",
        msg,
        re.I,
    )
    if not match:
        return

    name = match.group(1) or match.group(4)
    music_type = match.group(2) or match.group(3)
    if not name:
        await whatSong.finish(
            (
                MessageSegment.text("迪拉熊不知道哦~"),
                MessageSegment.image(Path("./Static/Maimai/Function/2.png")),
            ),
            at_sender=True,
        )

    songList = await get_music_data()
    result, song_info = await get_info_by_name(name, music_type, songList)
    if result == 1:
        if isinstance(song_info, set):
            msg = f"迪拉熊找到啦~结果有：\r\n{"\r\n".join(song_info)}"
            await whatSong.finish(MessageSegment.text(msg))
    elif result == 2:
        await whatSong.finish(
            (
                MessageSegment.text("迪拉熊不知道哦~"),
                MessageSegment.image(Path("./Static/Maimai/Function/2.png")),
            ),
            at_sender=True,
        )
    elif result == 3:
        await whatSong.finish(
            (
                MessageSegment.text("结果太多啦，缩小范围再试试吧~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    await whatSong.send(
        MessageSegment.text("迪拉熊绘制中，稍等一下mai~"), at_sender=True
    )
    if song_info["basic_info"]["genre"] == "宴会場":
        start_time = time.perf_counter()
        img = await utage_music_info(song_data=song_info)
    else:
        start_time = time.perf_counter()
        img = await music_info(song_data=song_info)
    end_time = time.perf_counter()
    msg = (
        MessageSegment.image(img),
        MessageSegment.text(f"绘制用时：{end_time - start_time:.2f}秒"),
    )
    await whatSong.send(msg)


# 查看别名
@aliasSearch.handle()
async def _(event: MessageEvent):
    msg = event.get_plaintext()
    match = re.fullmatch(
        r"(?:alias|查看?别名)\s*(.+)|(.+)有(什么|哪些)别名？?", msg, re.I
    )
    if not match:
        return

    name = match.group(1) or match.group(2)
    if not name:
        await aliasSearch.finish(
            (
                MessageSegment.text("迪拉熊不知道哦~"),
                MessageSegment.image(Path("./Static/Maimai/Function/2.png")),
            ),
            at_sender=True,
        )

    songList = await get_music_data()
    result, song_info = await get_info_by_name(name, None, songList)
    if result == 1:
        if isinstance(song_info, set):
            msg = f"迪拉熊找到啦~结果有：\r\n{"\r\n".join(song_info)}"
            await aliasSearch.finish(MessageSegment.text(msg))
    elif result == 2:
        await aliasSearch.finish(
            (
                MessageSegment.text("迪拉熊不知道哦~"),
                MessageSegment.image(Path("./Static/Maimai/Function/2.png")),
            ),
            at_sender=True,
        )
    elif result == 3:
        await aliasSearch.finish(
            (
                MessageSegment.text("结果太多啦，缩小范围再试试吧~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    song_id = int(song_info["id"]) - 10000
    alias = set()
    alias.add(song_info["id"])
    alias_list = await get_alias_list_lxns()
    for d in alias_list["aliases"]:
        if d["song_id"] == song_id:
            alias |= set(d["aliases"])
    alias_list = await get_alias_list_xray()
    for id, d in alias_list.items():
        if int(id) - 10000 == song_id:
            alias |= set(d)
    alias_list = await get_alias_list_ycn()
    for d in alias_list["content"]:
        if d["SongID"] - 10000 == song_id:
            alias |= set(d["Alias"])
    if not alias:
        msg = (
            MessageSegment.text("迪拉熊不知道哦~"),
            MessageSegment.image(Path("./Static/Maimai/Function/2.png")),
        )
        await aliasSearch.send(MessageSegment.text(msg), at_sender=True)
    else:
        song_alias = "\r\n".join(sorted(alias))
        msg = f"迪拉熊找到啦~别名有：\r\n{song_alias}\r\n\r\n感谢落雪查分器、X-ray Bot及YuzuChaN Bot提供数据支持"
        await aliasSearch.send(MessageSegment.text(msg))


@all_frame.handle()
async def _():
    path = "./Static/maimai/allFrame.png"
    await all_frame.send(MessageSegment.image(Path(path)))


@all_plate.handle()
async def _():
    path = "./Static/maimai/allPlate.png"
    await all_plate.send(MessageSegment.image(Path(path)))


@set_plate.handle()
async def _(event: MessageEvent):
    qq = event.get_user_id()
    msg = event.get_plaintext()
    id = re.search(r"\d+", msg).group()
    plate_path = f"./Cache/Plate/{id}.png"
    if not os.path.exists(plate_path):
        async with aiohttp.ClientSession(conn_timeout=3) as session:
            async with session.get(
                f"https://assets2.lxns.net/maimai/plate/{int(id)}.png"
            ) as resp:
                if resp.status != 200:
                    msg = (
                        MessageSegment.text("迪拉熊没有找到合适的姓名框"),
                        MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
                    )
                    await set_plate.finish(msg, at_sender=True)

                with open(plate_path, "wb") as fd:
                    async for chunk in resp.content.iter_chunked(1024):
                        fd.write(chunk)

    with shelve.open("./data/user_config.db") as config:
        if qq not in config:
            config.setdefault(qq, {"plate": id})
        else:
            cfg = config[qq]
            if "plate" not in config[qq]:
                cfg.setdefault("plate", id)
            else:
                cfg["plate"] = id
            config[qq] = cfg

    msg = "迪拉熊帮你换好啦~"
    await set_plate.send(MessageSegment.text(msg), at_sender=True)


@set_frame.handle()
async def _(event: MessageEvent):
    qq = event.get_user_id()
    msg = event.get_plaintext()
    id = re.search(r"\d+", msg).group()
    dir_path = "./Static/maimai/Frame/"
    file_name = f"UI_Frame_{id}.png"
    file_path = Path(dir_path) / file_name
    if os.path.exists(file_path):
        with shelve.open("./data/user_config.db") as config:
            if qq not in config:
                config.setdefault(qq, {"frame": id})
            else:
                cfg = config[qq]
                if "frame" not in config[qq]:
                    cfg.setdefault("frame", id)
                else:
                    cfg["frame"] = id
                config[qq] = cfg

        msg = MessageSegment.text("迪拉熊帮你换好啦~")
    else:
        msg = (
            MessageSegment.text("迪拉熊没有找到合适的背景"),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
    await set_frame.send(msg, at_sender=True)


@ratj_on.handle()
async def _(event: MessageEvent):
    qq = event.get_user_id()
    with shelve.open("./data/user_config.db") as config:
        if qq not in config:
            config.setdefault(qq, {"rating_tj": True})
        else:
            cfg = config[qq]
            if "rating_tj" not in config[qq]:
                cfg.setdefault("rating_tj", True)
            else:
                cfg["rating_tj"] = True
            config[qq] = cfg

    msg = "迪拉熊帮你改好啦~"
    await ratj_on.send(MessageSegment.text(msg), at_sender=True)


@ratj_off.handle()
async def _(event: MessageEvent):
    qq = event.get_user_id()
    with shelve.open("./data/user_config.db") as config:
        if qq not in config:
            config.setdefault(qq, {"rating_tj": False})
        else:
            cfg = config[qq]
            if "rating_tj" not in config[qq]:
                cfg.setdefault("rating_tj", False)
            else:
                cfg["rating_tj"] = False
            config[qq] = cfg

    msg = "迪拉熊帮你改好啦~"
    await ratj_off.send(MessageSegment.text(msg), at_sender=True)


@allow_other_on.handle()
async def _(event: MessageEvent):
    qq = event.get_user_id()
    with shelve.open("./data/user_config.db") as config:
        if qq not in config:
            config.setdefault(qq, {"allow_other": True})
        else:
            cfg = config[qq]
            if "allow_other" not in config[qq]:
                cfg.setdefault("allow_other", True)
            else:
                cfg["allow_other"] = True
            config[qq] = cfg

    msg = "迪拉熊帮你改好啦~"
    await allow_other_on.send(MessageSegment.text(msg), at_sender=True)


@allow_other_off.handle()
async def _(event: MessageEvent):
    qq = event.get_user_id()
    with shelve.open("./data/user_config.db") as config:
        if qq not in config:
            config.setdefault(qq, {"allow_other": False})
        else:
            cfg = config[qq]
            if "allow_other" not in config[qq]:
                cfg.setdefault("allow_other", False)
            else:
                cfg["allow_other"] = False
            config[qq] = cfg

    msg = "迪拉熊帮你改好啦~"
    await allow_other_off.send(MessageSegment.text(msg), at_sender=True)
