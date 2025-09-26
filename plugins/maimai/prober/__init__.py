import asyncio
import math
import re
from io import BytesIO
from pathlib import Path
from typing import Optional

import numpy as np
from grpc import RpcError, StatusCode
from nonebot import on_regex
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
from numpy import random
from rapidfuzz import fuzz, process
from requests import HTTPError

from util.config import config
from util.data import (
    get_alias_list_lxns,
    get_alias_list_xray,
    get_alias_list_ycn,
    get_chart_stats,
    get_music_data_df,
)
from util.resources import get_frame, get_icon, get_plate
from .bests_gen import (
    compute_record,
    dxscore_proc,
    find_song_by_id,
    generate_wcb,
    generatebests,
    get_fit_diff,
    get_page_records,
    ratings,
    records_filter,
)
from .database import user_config_manager
from .diving_fish import get_player_record, get_player_records
from .info_gen import (
    achv_info,
    chart_info,
    score_info,
    utage_chart_info,
    utage_score_info,
)
from .limekuma_client import BestsApiClient, ListApiClient

best50 = on_regex(r"^dlxb?50$", re.I)
ani50 = on_regex(r"^dlxani(50)?$", re.I)
best40 = on_regex(r"^dlxb?40$", re.I)
fit50 = on_regex(r"dlxf50$", re.I)
dxs50 = on_regex(r"dlxs50$", re.I)
star50 = on_regex(r"^dlxx50(\s*[1-5])+$", re.I)
rate50 = on_regex(r"^dlxr50(\s*(s{1,3}(p|\+)?|a{1,3}|b{1,3}|[cd]))+?$", re.I)
ap50 = on_regex(r"^dlxap(50)?$", re.I)
fc50 = on_regex(r"^dlxfc(50)?$", re.I)
cf50 = on_regex(r"^dlxcf(50)?$", re.I)
sd50 = on_regex(r"^dlx(s|f)d(50)?$", re.I)
all50 = on_regex(r"^dlx(all?(50)?|b)$", re.I)
rr50 = on_regex(r"^dlxrr(50)?(\s*\d+)?$", re.I)
sunnlist = on_regex(r"^dlx(sunn?|cun|寸|🤏)(\s*\d+?)?$", re.I)
locklist = on_regex(r"^dlx(suo|锁|🔒)(\s*\d+?)?$", re.I)

chartinfo = on_regex(
    r"^((chart|id|search|查歌)\s*((dx|sd|标准?|[左右]|宴)\s*)?.+|"
    r"((dx|sd|标准?|宴)\s*)?.+是什么歌？?)$",
    re.I,
)
scoreinfo = on_regex(r"^(score|info)\s*((dx|sd|标准?|宴)\s*)?.", re.I)
achvinfo = on_regex(
    r"^(achv|分数表格?)\s*((绿|黄|红|紫|白)\s*((dx|sd|标准?)\s*)?|([左右]\s*)?).",
    re.I,
)
songreq = on_regex(r"^(迪拉熊|dlx)点歌\s*.", re.I)
randsong = on_regex(
    r"^(rand|随(歌|个|首|张))\s*(绿|黄|红|紫|白)?\s*\d+(\.\d|\+)?$", re.I
)
maiwhat = on_regex("^mai什么$", re.I)

complist = on_regex(
    r"^(list|完成列?表)\s*(\d+\+?|真|超|檄|橙|晓|桃|樱|紫|堇|白|雪|辉|舞|熊|华|爽|煌|宙|星|祭|祝|双|宴|镜|彩)(\s*\d+)?$",
    re.I,
)

alias_search = on_regex(
    r"^((alias|查看?别(名|称))\s*.+|.+有(什么|哪些)别(名|称)？?)$", re.I
)

all_plate = on_regex(r"^(迪拉熊|dlx)?(plates?|看姓名框)$", re.I)
all_frame = on_regex(r"^(迪拉熊|dlx)?(frames?|看背景)$", re.I)
all_icon = on_regex(r"^(迪拉熊|dlx)?(icons?|看头像)$", re.I)

set_plate = on_regex(r"^(迪拉熊|dlx)?(setplate|设置?姓名框)\s*\d{6}$", re.I)
set_frame = on_regex(r"^(迪拉熊|dlx)?(setframe|设置?背景)\s*\d{6}$", re.I)
set_icon = on_regex(r"^(迪拉熊|dlx)?(seticon|设置?头像)\s*\d{6}$", re.I)

rasug_on = on_regex(r"^(迪拉熊|dlx)?(开启?|启用)分数推荐$", re.I)
rasug_off = on_regex(r"^(迪拉熊|dlx)?(关闭?|禁用)分数推荐$", re.I)

allow_other_on = on_regex(r"^(迪拉熊|dlx)?(开启?|启用|允许)代查$", re.I)
allow_other_off = on_regex(r"^(迪拉熊|dlx)?(关闭?|禁用|禁止)代查$", re.I)

set_source = on_regex(
    r"^(迪拉熊|dlx)?((切|更)?换|设置)((数据)?源|查分器)\s*(落雪|水鱼)$", re.I
)
set_token = on_regex(r"^(迪拉熊|dlx)?(绑定|bind)\s*(落雪|水鱼)\s*.", re.I)


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

    alias_map = dict()

    async def process_lxns(alias_map: dict[str, list[str]]):
        alias_list = await get_alias_list_lxns()
        for info in alias_list["aliases"]:
            song_id = str(info["song_id"])
            for alias in info["aliases"]:
                alias_map.setdefault(alias, list())
                if song_id in alias_map[alias]:
                    continue
                alias_map[alias].append(song_id)

    async def process_xray(alias_map: dict[str, list[str]]):
        alias_list = await get_alias_list_xray()
        for song_id, info in alias_list.items():
            for alias in info:
                alias_map.setdefault(alias, list())
                if song_id in alias_map[alias]:
                    continue
                alias_map[alias].append(song_id)

    async def process_ycn(alias_map: dict[str, list[str]]):
        alias_list = await get_alias_list_ycn()
        for info in alias_list["content"]:
            song_id = str(info["SongID"])
            for alias in info["Alias"]:
                alias_map.setdefault(alias, list())
                if song_id in alias_map[alias]:
                    continue
                alias_map[alias].append(song_id)

    await asyncio.gather(
        process_lxns(alias_map), process_xray(alias_map), process_ycn(alias_map)
    )

    results = process.extract(
        name, alias_map.keys(), scorer=fuzz.QRatio, score_cutoff=100
    )
    filtered = {
        id for ids in [alias_map[alias] for alias, _, _ in results] for id in ids
    }
    matched_ids = list(filtered)
    if len(matched_ids) > 0:
        return matched_ids

    results = process.extract(
        name, alias_map.keys(), scorer=fuzz.WRatio, score_cutoff=80
    )
    filtered = {
        id for ids in [alias_map[alias] for alias, _, _ in results] for id in ids
    }
    matched_ids = list(filtered)

    # 芝士排序
    # sorted_matched_ids = sorted(matched_ids, key=int)

    # 芝士输出
    return matched_ids


async def records_to_bests(
    records: Optional[list],
    songList,
    fc_rules: Optional[list] = None,
    rate_rules: Optional[list] = None,
    is_fit: bool = False,
    is_sd: bool = False,
    is_dxs: bool = False,
    is_all: bool = False,
    is_old: bool = False,
    dx_star_count: Optional[str] = None,
    rating: int = 0,
):
    sd = list()
    dx = list()
    charts = await get_chart_stats()
    mask_enabled = False

    def default_k(x):
        return (x["ra"], x["ds"], x["achievements"])

    if not records:
        for song in songList:
            if len(song["id"]) > 5:
                continue
            for i, j in enumerate(song["ds"]):
                record = {
                    "achievements": 101,
                    "ds": j,
                    "dxScore": np.sum(song["charts"][i]["notes"]) * 3,
                    "fc": "fsdp",
                    "fs": "app",
                    "level": str(),
                    "level_index": i,
                    "level_label": [
                        "Basic",
                        "Advanced",
                        "Expert",
                        "Master",
                        "ReMASTER",
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
        sd.sort(key=default_k, reverse=True)
        dx.sort(key=default_k, reverse=True)
        if rating:
            while (
                np.sum(d["ra"] for d in sd[:35]) + np.sum(d["ra"] for d in dx[:15])
                > rating
            ):
                if (dx and sd and dx[0]["ra"] > sd[0]["ra"]) or (dx and not sd):
                    b = dx
                elif sd:
                    b = sd
                else:
                    continue
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
                if not song_data:
                    continue
                record["achievements"] = (
                    record["dxScore"]
                    / (np.sum(song_data["charts"][record["level_index"]]["notes"]) * 3)
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
                    np.sum(song_data["charts"][record["level_index"]]["notes"]) * 3
                )
                _, stars = dxscore_proc(record["dxScore"], sum_dxscore)
                if str(stars) not in dx_star_count:
                    continue
        if is_old:
            if record["achievements"] > 0 and record["dxScore"] == 0:
                mask_enabled = True
                continue
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
        all_records = sorted(dx, key=default_k, reverse=True)
        dx = list()
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

        def k(x):
            return (x["ra"] * (1 + x["diff"] / 10), x["ds"], x["achievements"])
    else:
        k = default_k
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

    def k(x):
        return (x["preferred"], x["ra"] - x["s_ra"], x["ds"], x["achievements"])

    b35 = sorted(sd, key=k, reverse=True)[:35]
    b15 = sorted(dx, key=k, reverse=True)[:15]
    return b35, b15, mask_enabled


def get_ra_in(rate: str) -> float:
    return ratings[rate][1]


def get_ra_in_old(rate: str) -> float:
    return ratings[rate][2]


async def get_info_by_name(name, music_type, songList):
    rep_ids = await find_songid_by_alias(name, songList)
    if not rep_ids:
        return 2, None
    rep_id = name
    if music_type or name not in rep_ids:
        for song_id in rep_ids.copy():
            id_int = int(song_id)
            song_info = find_song_by_id(song_id, songList)
            if not song_info:
                rep_ids.remove(song_id)
                other_id = (
                    str(id_int + 10000) if id_int < 10000 else str(id_int % 10000)
                )
                song_info = find_song_by_id(other_id, songList)
                if not song_info:
                    continue
                if not check_type(song_info, music_type):
                    continue
                rep_ids.append(other_id)
                song_id = other_id
            else:
                if not check_type(song_info, music_type):
                    rep_ids.remove(song_id)
                    continue
                if song_info["basic_info"]["genre"] == "宴会場":
                    continue
                elif song_info["type"] == "DX":
                    other_id = str(id_int % 10000)
                elif song_info["type"] == "SD":
                    other_id = str(id_int + 10000)
                else:
                    continue
                if other_id in rep_ids:
                    continue
                other_info = find_song_by_id(other_id, songList)
                if other_info:
                    if not check_type(other_info, music_type):
                        continue
                    rep_ids.append(other_id)
        if not rep_ids:
            return 2, None
        elif len(rep_ids) > 16:
            return 3, rep_ids
        elif len(rep_ids) > 1:
            output_lst = set()
            song_info = None
            for song_id in sorted(rep_ids, key=int):
                song_info = find_song_by_id(song_id, songList)
                if not song_info:
                    continue
                song_title = f"{song_info['id']}：{song_info['title']}"
                output_lst.add(song_title)
            if not song_info:
                return 2, None
            return 1, output_lst if len(output_lst) > 1 else song_info

        rep_id = rep_ids[0]
    song_info = find_song_by_id(rep_id, songList)
    if not song_info:
        return 2, None

    return 0, song_info


def check_type(song_info, music_type):
    if not music_type:
        return True
    if music_type.casefold() == "dx":
        if song_info["type"] == "DX":
            return True
    elif music_type.casefold() == "sd" or music_type == "标准" or music_type == "标":
        if song_info["type"] == "SD":
            return True
    elif music_type.casefold() == "宴":
        if song_info["basic_info"]["genre"] == "宴会場":
            return True
    return False


@best50.handle()
async def _(bot: Bot, event: MessageEvent):
    sender_qq = event.user_id
    target_qq = event.get_user_id()
    user_info = await bot.get_stranger_info(user_id=sender_qq)
    for message in event.get_message()["at"]:
        target_qq = message.data["qq"]
        if target_qq == event.get_user_id():
            continue
        if "isBlock" not in user_info and "isBlocked" not in user_info:
            sender_qq = target_qq
            break
        else:
            if await user_config_manager.get_config_value(
                target_qq, "allow_other", True
            ):
                break
    else:
        if target_qq != event.get_user_id():
            msg = (
                MessageSegment.at(sender_qq),
                MessageSegment.text(" "),
                MessageSegment.text("他不允许别人查询他的成绩mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/3.png")),
            )
            await best50.finish(msg)
    user_config = await user_config_manager.get_user_config(target_qq)
    frame = user_config["frame"]
    plate = user_config["plate"]
    icon = user_config["icon"]
    is_rating_tj = user_config["rating_tj"]
    source = user_config["source"]
    lx_personal_token = user_config["lx_personal_token"]
    if source == "lxns":
        source_name = "落雪"
        another_source_name = "水鱼"
    elif source == "diving-fish":
        source_name = "水鱼"
        another_source_name = "落雪"
    img_byte_arr = BytesIO()
    async with BestsApiClient() as client:
        try:
            if source == "lxns":
                params = {"dev_token": config.lx_token}
                if lx_personal_token:
                    params["personal_token"] = lx_personal_token
                else:
                    params["qq"] = int(target_qq)
                gen = client.get_from_lxns(**params)
            elif source == "diving-fish":
                params = {
                    "qq": int(target_qq),
                    "frame": int(frame),
                    "plate": int(plate),
                    "icon": int(icon),
                }
                gen = client.get_from_diving_fish(**params)
            else:
                return
            async for b in gen:
                img_byte_arr.write(b.data)
        except RpcError as err:
            if err.code() == StatusCode.NOT_FOUND:
                msg = (
                    MessageSegment.at(sender_qq),
                    MessageSegment.text(" "),
                    MessageSegment.text(
                        f"迪拉熊没有在{source_name}查分器上找到{
                            '你' if target_qq == event.get_user_id() else '他'
                        }的信息，可以试试发送“换源{another_source_name}”更换查分器mai~"
                    ),
                    MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
                )
            elif err.code() == StatusCode.PERMISSION_DENIED:
                msg = (
                    MessageSegment.at(sender_qq),
                    MessageSegment.text(" "),
                    MessageSegment.text(
                        f"{'你' if target_qq == event.get_user_id() else '他'}在{
                            source_name
                        }查分器启用了隐私，或者没有同意{
                            source_name
                        }查分器的用户协议mai~"
                    ),
                    MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
                )
            elif err.code() == StatusCode.UNAUTHENTICATED:
                msg = (
                    MessageSegment.at(sender_qq),
                    MessageSegment.text(" "),
                    MessageSegment.text(
                        f"{'你' if target_qq == event.get_user_id() else '他'}的{
                            source_name
                        }查分器绑定有点问题mai~"
                    ),
                    MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
                )
            else:
                msg = (
                    MessageSegment.text("（查分器出了点问题）"),
                    MessageSegment.image(Path("./Static/Maimai/Function/2.png")),
                )
            await best50.finish(msg)
    img_byte_arr.seek(0)
    img_bytes = img_byte_arr.getvalue()
    msg = (
        MessageSegment.at(sender_qq),
        MessageSegment.image(img_bytes),
    )
    await best50.send(msg)


@ani50.handle()
async def _(event: MessageEvent):
    target_qq = event.get_user_id()
    for message in event.get_message()["at"]:
        target_qq = message.data["qq"]
        if target_qq == event.get_user_id():
            continue
        if await user_config_manager.get_config_value(target_qq, "allow_other", True):
            break
    else:
        if target_qq != event.get_user_id():
            msg = (
                MessageSegment.text("他不允许别人查询他的成绩mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/3.png")),
            )
            await ani50.finish(msg, at_sender=True)
    user_config = await user_config_manager.get_user_config(target_qq)
    frame = user_config["frame"]
    plate = user_config["plate"]
    icon = user_config["icon"]
    source = user_config["source"]
    lx_personal_token = user_config["lx_personal_token"]
    if source == "lxns":
        source_name = "落雪"
        another_source_name = "水鱼"
    elif source == "diving-fish":
        source_name = "水鱼"
        another_source_name = "落雪"
    img_byte_arr = BytesIO()
    async with BestsApiClient() as client:
        try:
            if source == "lxns":
                params = {"dev_token": config.lx_token}
                if lx_personal_token:
                    params["personal_token"] = lx_personal_token
                else:
                    params["qq"] = int(target_qq)
                gen = client.get_anime_from_lxns(**params)
            elif source == "diving-fish":
                params = {
                    "qq": int(target_qq),
                    "frame": int(frame),
                    "plate": int(plate),
                    "icon": int(icon),
                }
                gen = client.get_anime_from_diving_fish(**params)
            else:
                return
            async for b in gen:
                img_byte_arr.write(b.data)
        except RpcError as err:
            if err.code() == StatusCode.NOT_FOUND:
                msg = (
                    MessageSegment.text(
                        f"迪拉熊没有在{source_name}查分器上找到{
                            '你' if target_qq == event.get_user_id() else '他'
                        }的信息，可以试试发送“换源{another_source_name}”更换查分器mai~"
                    ),
                    MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
                )
            elif err.code() == StatusCode.PERMISSION_DENIED:
                msg = (
                    MessageSegment.text(
                        f"{'你' if target_qq == event.get_user_id() else '他'}在{
                            source_name
                        }查分器启用了隐私或者没有同意{source_name}查分器的用户协议mai~"
                    ),
                    MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
                )
            elif err.code() == StatusCode.UNAUTHENTICATED:
                msg = (
                    MessageSegment.text(
                        f"{'你' if target_qq == event.get_user_id() else '他'}的{
                            source_name
                        }查分器绑定有点问题mai~"
                    ),
                    MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
                )
            else:
                msg = (
                    MessageSegment.text("（查分器出了点问题）"),
                    MessageSegment.image(Path("./Static/Maimai/Function/2.png")),
                )
            await ani50.finish(msg, at_sender=True)
    img_byte_arr.seek(0)
    img_bytes = img_byte_arr.getvalue()
    msg = (
        MessageSegment.at(target_qq),
        MessageSegment.image(img_bytes),
    )
    await ani50.send(msg)


@ap50.handle()
async def _(event: MessageEvent):
    target_qq = event.get_user_id()
    for message in event.get_message()["at"]:
        target_qq = message.data["qq"]
        if target_qq == event.get_user_id():
            continue
        if await user_config_manager.get_config_value(target_qq, "allow_other", True):
            break
    else:
        if target_qq != event.get_user_id():
            msg = (
                MessageSegment.text("他不允许别人查询他的成绩mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/3.png")),
            )
            await ap50.finish(msg, at_sender=True)
    data, status = await get_player_records(target_qq)
    if status == 400:
        msg = (
            MessageSegment.text(
                f"迪拉熊没有找到{'你' if target_qq == event.get_user_id() else '他'}的信息mai~"
            ),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await ap50.finish(msg, at_sender=True)
    elif not data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/Maimai/Function/2.png")),
        )
        await ap50.finish(msg, at_sender=True)
    records = data["records"]
    if not records:
        await ap50.finish(
            (
                MessageSegment.text(
                    f"{'你' if target_qq == event.get_user_id() else '他'}没有上传任何成绩mai~"
                ),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    songList = await get_music_data_df()
    ap35, ap15, _ = await records_to_bests(records, songList, ["ap", "app"])
    if not ap35 and not ap15:
        await ap50.finish(
            (
                MessageSegment.text(
                    f"{'你' if target_qq == event.get_user_id() else '他'}没有全完美的成绩mai~"
                ),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    nickname = data["nickname"]
    dani = data["additional_rating"]
    user_config = await user_config_manager.get_user_config(target_qq)
    frame = user_config["frame"]
    plate = user_config["plate"]
    icon = user_config["icon"]
    is_rating_tj = user_config["rating_tj"]
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
    msg = MessageSegment.image(img)
    await ap50.send(msg, at_sender=True)


@fc50.handle()
async def _(event: MessageEvent):
    target_qq = event.get_user_id()
    for message in event.get_message()["at"]:
        target_qq = message.data["qq"]
        if target_qq == event.get_user_id():
            continue
        if await user_config_manager.get_config_value(target_qq, "allow_other", True):
            break
    else:
        if target_qq != event.get_user_id():
            msg = (
                MessageSegment.text("他不允许别人查询他的成绩mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/3.png")),
            )
            await fc50.finish(msg, at_sender=True)
    data, status = await get_player_records(target_qq)
    if status == 400:
        msg = (
            MessageSegment.text(
                f"迪拉熊没有找到{'你' if target_qq == event.get_user_id() else '他'}的信息mai~"
            ),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await fc50.finish(msg, at_sender=True)
    elif not data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/Maimai/Function/2.png")),
        )
        await fc50.finish(msg, at_sender=True)
    records = data["records"]
    if not records:
        await fc50.finish(
            (
                MessageSegment.text(
                    f"{'你' if target_qq == event.get_user_id() else '他'}没有上传任何成绩mai~"
                ),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    songList = await get_music_data_df()
    fc35, fc15, _ = await records_to_bests(records, songList, ["fc", "fcp"])
    if not fc35 and not fc15:
        await fc50.finish(
            (
                MessageSegment.text(
                    f"{'你' if target_qq == event.get_user_id() else '他'}没有全连的成绩mai~"
                ),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    nickname = data["nickname"]
    dani = data["additional_rating"]
    user_config = await user_config_manager.get_user_config(target_qq)
    frame = user_config["frame"]
    plate = user_config["plate"]
    icon = user_config["icon"]
    is_rating_tj = user_config["rating_tj"]
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
    msg = MessageSegment.image(img)
    await fc50.send(msg, at_sender=True)


@fit50.handle()
async def _(event: MessageEvent):
    target_qq = event.get_user_id()
    for message in event.get_message()["at"]:
        target_qq = message.data["qq"]
        if target_qq == event.get_user_id():
            continue
        if await user_config_manager.get_config_value(target_qq, "allow_other", True):
            break
    else:
        if target_qq != event.get_user_id():
            msg = (
                MessageSegment.text("他不允许别人查询他的成绩mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/3.png")),
            )
            await fit50.finish(msg, at_sender=True)
    data, status = await get_player_records(target_qq)
    if status == 400:
        msg = (
            MessageSegment.text(
                f"迪拉熊没有找到{'你' if target_qq == event.get_user_id() else '他'}的信息mai~"
            ),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await fit50.finish(msg, at_sender=True)
    elif not data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/Maimai/Function/2.png")),
        )
        await fit50.finish(msg, at_sender=True)
    records = data["records"]
    if not records:
        await fit50.finish(
            (
                MessageSegment.text(
                    f"{'你' if target_qq == event.get_user_id() else '他'}没有上传任何成绩mai~"
                ),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    songList = await get_music_data_df()
    b35, b15, mask_enabled = await records_to_bests(records, songList, is_fit=True)
    if not b35 and not b15:
        if mask_enabled:
            msg = f"迪拉熊无法获取{'你' if target_qq == event.get_user_id() else '他'}的真实成绩mai~"
        else:
            msg = f"{'你' if target_qq == event.get_user_id() else '他'}没有上传任何对得上的成绩mai~"
        await fit50.finish(
            (
                MessageSegment.text(msg),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    nickname = data["nickname"]
    dani = data["additional_rating"]
    user_config = await user_config_manager.get_user_config(target_qq)
    frame = user_config["frame"]
    plate = user_config["plate"]
    icon = user_config["icon"]
    is_rating_tj = user_config["rating_tj"]
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
    msg = MessageSegment.image(img)
    await fit50.send(msg, at_sender=True)


@best40.handle()
async def _(event: MessageEvent):
    target_qq = event.get_user_id()
    for message in event.get_message()["at"]:
        target_qq = message.data["qq"]
        if target_qq == event.get_user_id():
            continue
        if await user_config_manager.get_config_value(target_qq, "allow_other", True):
            break
    else:
        if target_qq != event.get_user_id():
            msg = (
                MessageSegment.text("他不允许别人查询他的成绩mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/3.png")),
            )
            await best40.finish(msg, at_sender=True)
    data, status = await get_player_records(target_qq)
    if status == 400:
        msg = (
            MessageSegment.text(
                f"迪拉熊没有找到{'你' if target_qq == event.get_user_id() else '他'}的信息mai~"
            ),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await best40.finish(msg, at_sender=True)
    elif not data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/Maimai/Function/2.png")),
        )
        await best40.finish(msg, at_sender=True)
    records = data["records"]
    if not records:
        await best40.finish(
            (
                MessageSegment.text(
                    f"{'你' if target_qq == event.get_user_id() else '他'}没有上传任何成绩mai~"
                ),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    songList = await get_music_data_df()
    b25, b15, _ = await records_to_bests(records, songList, is_old=True)
    nickname = data["nickname"]
    dani = data["additional_rating"]
    user_config = await user_config_manager.get_user_config(target_qq)
    frame = user_config["frame"]
    plate = user_config["plate"]
    icon = user_config["icon"]
    is_rating_tj = user_config["rating_tj"]
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
    msg = MessageSegment.image(img)
    await best40.send(msg, at_sender=True)


@rate50.handle()
async def _(event: MessageEvent):
    target_qq = event.get_user_id()
    for message in event.get_message()["at"]:
        target_qq = message.data["qq"]
        if target_qq == event.get_user_id():
            continue
        if await user_config_manager.get_config_value(target_qq, "allow_other", True):
            break
    else:
        if target_qq != event.get_user_id():
            msg = (
                MessageSegment.text("他不允许别人查询他的成绩mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/3.png")),
            )
            await rate50.finish(msg, at_sender=True)
    data, status = await get_player_records(target_qq)
    if status == 400:
        msg = (
            MessageSegment.text(
                f"迪拉熊没有找到{'你' if target_qq == event.get_user_id() else '他'}的信息mai~"
            ),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await rate50.finish(msg, at_sender=True)
    elif not data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/Maimai/Function/2.png")),
        )
        await rate50.finish(msg, at_sender=True)
    records = data["records"]
    if not records:
        await rate50.finish(
            (
                MessageSegment.text(
                    f"{'你' if target_qq == event.get_user_id() else '他'}没有上传任何成绩mai~"
                ),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    msg_text = event.get_plaintext().replace("+", "p").casefold()
    rate_rules = re.findall(r"s{1,3}p?|a{1,3}|b{1,3}|[cd]", msg_text, re.I)
    songList = await get_music_data_df()
    rate35, rate15, _ = await records_to_bests(records, songList, rate_rules=rate_rules)
    if not rate35 and not rate15:
        await rate50.finish(
            (
                MessageSegment.text(
                    f"{'你' if target_qq == event.get_user_id() else '他'}没有上传任何对得上的成绩mai~"
                ),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    nickname = data["nickname"]
    dani = data["additional_rating"]
    user_config = await user_config_manager.get_user_config(target_qq)
    frame = user_config["frame"]
    plate = user_config["plate"]
    icon = user_config["icon"]
    is_rating_tj = user_config["rating_tj"]
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
    msg = MessageSegment.image(img)
    await rate50.send(msg, at_sender=True)


@dxs50.handle()
async def _(event: MessageEvent):
    target_qq = event.get_user_id()
    for message in event.get_message()["at"]:
        target_qq = message.data["qq"]
        if target_qq == event.get_user_id():
            continue
        if await user_config_manager.get_config_value(target_qq, "allow_other", True):
            break
    else:
        if target_qq != event.get_user_id():
            msg = (
                MessageSegment.text("他不允许别人查询他的成绩mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/3.png")),
            )
            await dxs50.finish(msg, at_sender=True)
    data, status = await get_player_records(target_qq)
    if status == 400:
        msg = (
            MessageSegment.text(
                f"迪拉熊没有找到{'你' if target_qq == event.get_user_id() else '他'}的信息mai~"
            ),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await dxs50.finish(msg, at_sender=True)
    elif not data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/Maimai/Function/2.png")),
        )
        await dxs50.finish(msg, at_sender=True)
    records = data["records"]
    if not records:
        await dxs50.finish(
            (
                MessageSegment.text(
                    f"{'你' if target_qq == event.get_user_id() else '他'}没有上传任何成绩mai~"
                ),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    songList = await get_music_data_df()
    dxs35, dxs15, mask_enabled = await records_to_bests(records, songList, is_dxs=True)
    if not dxs35 and not dxs15:
        if mask_enabled:
            msg = f"迪拉熊无法获取{'你' if target_qq == event.get_user_id() else '他'}的真实成绩mai~"
        else:
            msg = f"{'你' if target_qq == event.get_user_id() else '他'}没有上传任何对得上的成绩mai~"
        await dxs50.finish(
            (
                MessageSegment.text(msg),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    nickname = data["nickname"]
    dani = data["additional_rating"]
    user_config = await user_config_manager.get_user_config(target_qq)
    frame = user_config["frame"]
    plate = user_config["plate"]
    icon = user_config["icon"]
    is_rating_tj = user_config["rating_tj"]
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
    msg = MessageSegment.image(img)
    await dxs50.send(msg, at_sender=True)


@star50.handle()
async def _(event: MessageEvent):
    target_qq = event.get_user_id()
    for message in event.get_message()["at"]:
        target_qq = message.data["qq"]
        if target_qq == event.get_user_id():
            continue
        if await user_config_manager.get_config_value(target_qq, "allow_other", True):
            break
    else:
        if target_qq != event.get_user_id():
            msg = (
                MessageSegment.text("他不允许别人查询他的成绩mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/3.png")),
            )
            await star50.finish(msg, at_sender=True)
    data, status = await get_player_records(target_qq)
    if status == 400:
        msg = (
            MessageSegment.text(
                f"迪拉熊没有找到{'你' if target_qq == event.get_user_id() else '他'}的信息mai~"
            ),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await star50.finish(msg, at_sender=True)
    elif not data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/Maimai/Function/2.png")),
        )
        await star50.finish(msg, at_sender=True)
    records = data["records"]
    if not records:
        await star50.finish(
            (
                MessageSegment.text(
                    f"{'你' if target_qq == event.get_user_id() else '他'}没有上传任何成绩mai~"
                ),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    songList = await get_music_data_df()
    find = re.fullmatch(r"dlxx50((?:\s*[1-5])+)", event.get_plaintext().strip(), re.I)
    star35, star15, mask_enabled = await records_to_bests(
        records, songList, is_dxs=True, dx_star_count=find.group(1)
    )
    if not star35 and not star15:
        if mask_enabled:
            msg = f"迪拉熊无法获取{'你' if target_qq == event.get_user_id() else '他'}的真实成绩mai~"
        else:
            msg = f"{'你' if target_qq == event.get_user_id() else '他'}没有上传任何对得上的成绩mai~"
        await star50.finish(
            (
                MessageSegment.text(msg),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    nickname = data["nickname"]
    dani = data["additional_rating"]
    user_config = await user_config_manager.get_user_config(target_qq)
    frame = user_config["frame"]
    plate = user_config["plate"]
    icon = user_config["icon"]
    is_rating_tj = user_config["rating_tj"]
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
    msg = MessageSegment.image(img)
    await star50.send(msg, at_sender=True)


@cf50.handle()
async def _(event: MessageEvent):
    sender_qq = event.get_user_id()
    target_qq = None
    for message in event.get_message()["at"]:
        target_qq = message.data["qq"]
        if target_qq == sender_qq:
            continue
        if await user_config_manager.get_config_value(target_qq, "allow_other", True):
            break
    else:
        if target_qq != sender_qq:
            msg = (
                MessageSegment.text("他不允许别人查询他的成绩mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/3.png")),
            )
            await cf50.finish(msg, at_sender=True)
    if target_qq is None or target_qq == sender_qq:
        msg = (
            MessageSegment.text("你没有比较任何人mai~"),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await cf50.finish(msg, at_sender=True)
    sender_data, status = await get_player_records(sender_qq)
    if status == 400:
        msg = (
            MessageSegment.text("迪拉熊没有找到你的信息mai~"),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await cf50.finish(msg, at_sender=True)
    elif status == 403:
        msg = (
            MessageSegment.text("你在查分器启用了隐私或者没有同意查分器的用户协议mai~"),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await cf50.finish(msg, at_sender=True)
    elif not sender_data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/Maimai/Function/2.png")),
        )
        await cf50.finish(msg, at_sender=True)
    target_data, status = await get_player_records(target_qq)
    if status == 400:
        msg = (
            MessageSegment.text("迪拉熊没有找到他的信息mai~"),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await cf50.finish(msg, at_sender=True)
    elif status == 403:
        msg = (
            MessageSegment.text("他在查分器启用了隐私或者没有同意查分器的用户协议mai~"),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await cf50.finish(msg, at_sender=True)
    elif not target_data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/Maimai/Function/2.png")),
        )
        await cf50.finish(msg, at_sender=True)
    songList = await get_music_data_df()
    sender_records = sender_data["records"]
    if not sender_records:
        await cf50.finish(
            (
                MessageSegment.text("你没有上传任何成绩mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    target_records = target_data["records"]
    if not target_records:
        await cf50.finish(
            (
                MessageSegment.text("他没有上传任何成绩mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    songList = await get_music_data_df()
    b35, b15, mask_enabled = await compare_bests(
        sender_records, target_records, songList
    )
    if not b35 and not b15:
        if mask_enabled:
            msg = "迪拉熊无法获取真实成绩mai~"
        else:
            msg = "你们没有上传任何可以比较的成绩mai~"
        await cf50.finish(
            (
                MessageSegment.text(msg),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    nickname = target_data["nickname"]
    dani = target_data["additional_rating"]
    user_config = await user_config_manager.get_user_config(target_qq)
    frame = user_config["frame"]
    plate = user_config["plate"]
    icon = user_config["icon"]
    is_rating_tj = user_config["rating_tj"]
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
    msg = MessageSegment.image(img)
    await cf50.send(msg, at_sender=True)


@sd50.handle()
async def _(event: MessageEvent):
    target_qq = event.get_user_id()
    for message in event.get_message()["at"]:
        target_qq = message.data["qq"]
        if target_qq == event.get_user_id():
            continue
        if await user_config_manager.get_config_value(target_qq, "allow_other", True):
            break
    else:
        if target_qq != event.get_user_id():
            msg = (
                MessageSegment.text("他不允许别人查询他的成绩mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/3.png")),
            )
            await sd50.finish(msg, at_sender=True)
    data, status = await get_player_records(target_qq)
    if status == 400:
        msg = (
            MessageSegment.text(
                f"迪拉熊没有找到{'你' if target_qq == event.get_user_id() else '他'}的信息mai~"
            ),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await sd50.finish(msg, at_sender=True)
    elif not data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/Maimai/Function/2.png")),
        )
        await sd50.finish(msg, at_sender=True)
    records = data["records"]
    if not records:
        await sd50.finish(
            (
                MessageSegment.text(
                    f"{'你' if target_qq == event.get_user_id() else '他'}没有上传任何成绩mai~"
                ),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    songList = await get_music_data_df()
    b35, b15, _ = await records_to_bests(records, songList, is_sd=True)
    if not b35 and not b15:
        await sd50.finish(
            (
                MessageSegment.text(
                    f"{'你' if target_qq == event.get_user_id() else '他'}没有上传任何对得上的成绩mai~"
                ),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    nickname = data["nickname"]
    dani = data["additional_rating"]
    user_config = await user_config_manager.get_user_config(target_qq)
    frame = user_config["frame"]
    plate = user_config["plate"]
    icon = user_config["icon"]
    is_rating_tj = user_config["rating_tj"]
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
    msg = MessageSegment.image(img)
    await sd50.send(msg, at_sender=True)


@all50.handle()
async def _(event: MessageEvent):
    target_qq = event.get_user_id()
    for message in event.get_message()["at"]:
        target_qq = message.data["qq"]
        if target_qq == event.get_user_id():
            continue
        if await user_config_manager.get_config_value(target_qq, "allow_other", True):
            break
    else:
        if target_qq != event.get_user_id():
            msg = (
                MessageSegment.text("他不允许别人查询他的成绩mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/3.png")),
            )
            await all50.finish(msg, at_sender=True)
    data, status = await get_player_records(target_qq)
    if status == 400:
        msg = (
            MessageSegment.text(
                f"迪拉熊没有找到{'你' if target_qq == event.get_user_id() else '他'}的信息mai~"
            ),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await all50.finish(msg, at_sender=True)
    elif not data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/Maimai/Function/2.png")),
        )
        await all50.finish(msg, at_sender=True)
    records = data["records"]
    if not records:
        await all50.finish(
            (
                MessageSegment.text(
                    f"{'你' if target_qq == event.get_user_id() else '他'}没有上传任何成绩mai~"
                ),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    songList = await get_music_data_df()
    all35, all15, _ = await records_to_bests(records, songList, is_all=True)
    nickname = data["nickname"]
    dani = data["additional_rating"]
    user_config = await user_config_manager.get_user_config(target_qq)
    frame = user_config["frame"]
    plate = user_config["plate"]
    icon = user_config["icon"]
    is_rating_tj = user_config["rating_tj"]
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
    msg = MessageSegment.image(img)
    await all50.send(msg, at_sender=True)


@rr50.handle()
async def _(event: MessageEvent):
    match = re.fullmatch(r"dlxrr(?:50)?\s*(\d+)", event.get_plaintext(), re.I)
    rating = 0
    if match:
        rating = int(match.group(1))
        if rating < 0:
            await rr50.finish(
                (
                    MessageSegment.text("DX分数太低了mai~"),
                    MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
                ),
                at_sender=True,
            )

    songList = await get_music_data_df()
    rr35, rr15, _ = await records_to_bests(
        None,
        songList,
        rating=rating,
    )
    if not rr35 and not rr15:
        await rr50.finish(
            (
                MessageSegment.text("DX分数好像不太对mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )

    nickname = "ｍａｉｍａｉ"
    dani = 22
    img = await generatebests(
        b35=rr35,
        b15=rr15,
        nickname=nickname,
        dani=dani,
        type="rr50",
        icon="1",
        frame=None,
        plate="1",
        is_rating_tj=False,
        songList=songList,
    )
    msg = MessageSegment.image(img)
    await rr50.send(msg, at_sender=True)


@sunnlist.handle()
async def _(event: MessageEvent):
    qq = event.get_user_id()
    data, status = await get_player_records(qq)
    if status == 400:
        msg = (
            MessageSegment.text("迪拉熊没有找到你的信息mai~"),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await sunnlist.finish(msg, at_sender=True)
    elif not data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/Maimai/Function/2.png")),
        )
        await sunnlist.finish(msg, at_sender=True)
    records = data["records"]
    if not records:
        await sunnlist.finish(
            (
                MessageSegment.text("你没有上传任何成绩mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    songList = await get_music_data_df()
    filted_records, mask_enabled = records_filter(
        records=records, is_sun=True, songList=songList
    )
    if not filted_records:
        if mask_enabled:
            msg = "迪拉熊无法获取你的真实成绩mai~"
        else:
            msg = "你没有上传任何对得上的成绩mai~"
        await sunnlist.finish(
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
    input_records = get_page_records(filted_records, page=page)
    nickname = data["nickname"]
    rating = data["rating"]
    dani = data["additional_rating"]
    user_config = await user_config_manager.get_user_config(qq)
    frame = user_config["frame"]
    plate = user_config["plate"]
    icon = user_config["icon"]
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
    msg = MessageSegment.image(img)
    await sunnlist.send(msg, at_sender=True)


@locklist.handle()
async def _(event: MessageEvent):
    qq = event.get_user_id()
    data, status = await get_player_records(qq)
    if status == 400:
        msg = (
            MessageSegment.text("迪拉熊没有找到你的信息mai~"),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await locklist.finish(msg, at_sender=True)
    elif not data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/Maimai/Function/2.png")),
        )
        await locklist.finish(msg, at_sender=True)
    records = data["records"]
    if not records:
        await locklist.finish(
            (
                MessageSegment.text("你没有上传任何成绩mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    songList = await get_music_data_df()
    filted_records, mask_enabled = records_filter(
        records=records, is_lock=True, songList=songList
    )
    if not filted_records:
        if mask_enabled:
            msg = "迪拉熊无法获取你的真实成绩mai~"
        else:
            msg = "你没有上传任何对得上的成绩mai~"
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
    input_records = get_page_records(filted_records, page=page)
    nickname = data["nickname"]
    rating = data["rating"]
    dani = data["additional_rating"]
    user_config = await user_config_manager.get_user_config(qq)
    frame = user_config["frame"]
    plate = user_config["plate"]
    icon = user_config["icon"]
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
    msg = MessageSegment.image(img)
    await locklist.send(msg, at_sender=True)


@complist.handle()
async def _(event: MessageEvent):
    qq = event.get_user_id()
    msg = event.get_plaintext()
    pattern = r"(?:(\d+\+?)|(真|超|檄|橙|晓|桃|樱|紫|堇|白|雪|辉|舞|熊|华|爽|煌|宙|星|祭|祝|双|宴|镜|彩))(?:\s*(\d+))?"
    match = re.search(pattern, msg)
    level = match.group(1)
    ds = None
    gen = match.group(2)
    if match.group(3):
        page = int(match.group(3))
        if page <= 0:
            page = 1
    else:
        page = 1
    user_config = await user_config_manager.get_user_config(qq)
    frame = user_config["frame"]
    plate = user_config["plate"]
    icon = user_config["icon"]
    source = user_config["source"]
    lx_personal_token = user_config["lx_personal_token"]
    if source == "lxns":
        source_name = "落雪"
        another_source_name = "水鱼"
    elif source == "diving-fish":
        source_name = "水鱼"
        another_source_name = "落雪"
    if level:
        if source == "lxns" and not lx_personal_token:
            msg = (
                MessageSegment.text("你还没有绑定落雪查分器mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            )
            await complist.finish(msg, at_sender=True)
        img_byte_arr = BytesIO()
        async with ListApiClient() as client:
            try:
                params = {"level": level, "page": page}
                if source == "lxns":
                    params["personal_token"] = lx_personal_token
                    gen = client.get_from_lxns(**params)
                elif source == "diving-fish":
                    params["token"] = config.df_token
                    params["qq"] = int(qq)
                    params["plate"] = int(plate)
                    params["icon"] = int(icon)
                    gen = client.get_from_diving_fish(**params)
                else:
                    return
                async for b in gen:
                    img_byte_arr.write(b.data)
            except RpcError as err:
                if err.code() == StatusCode.NOT_FOUND:
                    msg = (
                        MessageSegment.text(
                            f"迪拉熊没有在{
                                source_name
                            }查分器上找到你的信息，可以试试发送“换源{
                                another_source_name
                            }”更换查分器mai~"
                        ),
                        MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
                    )
                elif err.code() == StatusCode.PERMISSION_DENIED:
                    msg = (
                        MessageSegment.text(
                            f"你在{source_name}查分器启用了隐私或者没有同意{
                                source_name
                            }查分器的用户协议mai~"
                        ),
                        MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
                    )
                elif err.code() == StatusCode.UNAUTHENTICATED:
                    msg = (
                        MessageSegment.text(f"你的{source_name}查分器绑定有点问题mai~"),
                        MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
                    )
                elif err.code() == StatusCode.OUT_OF_RANGE:
                    msg = (
                        MessageSegment.text("你的完成表没有这么多页mai~"),
                        MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
                    )
                else:
                    msg = (
                        MessageSegment.text("（查分器出了点问题）"),
                        MessageSegment.image(Path("./Static/Maimai/Function/2.png")),
                    )
                await complist.finish(msg, at_sender=True)
        img_byte_arr.seek(0)
        img = img_byte_arr.getvalue()
    else:
        data, status = await get_player_records(qq)
        if status == 400:
            msg = (
                MessageSegment.text("迪拉熊没有找到你的信息mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            )
            await complist.finish(msg, at_sender=True)
        elif not data:
            msg = (
                MessageSegment.text("（查分器出了点问题）"),
                MessageSegment.image(Path("./Static/Maimai/Function/2.png")),
            )
            await complist.finish(msg, at_sender=True)
        records = data["records"]
        if not records:
            await complist.finish(
                (
                    MessageSegment.text("你没有上传任何成绩mai~"),
                    MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
                ),
                at_sender=True,
            )
        songList = await get_music_data_df()
        filted_records, _ = records_filter(
            records=records, level=level, ds=ds, gen=gen, songList=songList
        )
        if len(filted_records) == 0:
            await complist.finish(
                (
                    MessageSegment.text("你没有上传任何对得上的成绩mai~"),
                    MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
                ),
                at_sender=True,
            )

        all_page_num = math.ceil(len(filted_records) / 55)
        page = min(page, all_page_num)
        input_records = get_page_records(filted_records, page=page)
        rate_count = compute_record(records=filted_records)
        nickname = data["nickname"]
        rating = data["rating"]
        dani = data["additional_rating"]
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
    msg = MessageSegment.image(img)
    await complist.send(msg, at_sender=True)


@chartinfo.handle()
async def _(event: MessageEvent):
    msg = event.get_plaintext()
    match = re.fullmatch(
        r"(?:chart|id|search|查歌)\s*(?:(dx|sd|标准?|[左右])\s*)?(.+)|(?:(dx|sd|标准?)\s*)?(.+)是什么歌？?",
        msg,
        re.I,
    )
    if not match:
        return

    song = match.group(2) or match.group(4)
    if not song:
        return

    music_type = match.group(1) or match.group(3)
    side_index = 0
    if music_type and music_type in "左右":
        side_index = "左右".index(music_type)
        music_type = "宴"
    songList = await get_music_data_df()
    result, song_info = await get_info_by_name(song, music_type, songList)
    if result == 1:
        if isinstance(song_info, set):
            msg = f"迪拉熊找到了这些乐曲——\r\n{'\r\n'.join(song_info)}"
            await chartinfo.finish(msg)
    elif result == 2:
        await chartinfo.finish(
            (
                MessageSegment.text("迪拉熊没有找到对得上的乐曲mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    elif result == 3:
        await chartinfo.finish(
            (
                MessageSegment.text("结果太多啦，缩小范围再试试吧~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    if song_info["basic_info"]["genre"] == "宴会場":
        chart_count = len(song_info["charts"])
        if music_type == "宴" and chart_count < 2:
            await chartinfo.finish(
                (
                    MessageSegment.text("迪拉熊没有找到对得上的乐曲mai~"),
                    MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
                ),
                at_sender=True,
            )
        if not music_type and chart_count > 1:
            await chartinfo.finish(
                (
                    MessageSegment.text("你没有告诉迪拉熊是哪一边的谱面mai~"),
                    MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
                ),
                at_sender=True,
            )
        img = await utage_chart_info(song_data=song_info, index=side_index)
    else:
        img = await chart_info(song_data=song_info)
    msg = (
        MessageSegment.text(f"{song_info['id']}：{song_info['title']}"),
        MessageSegment.image(img),
    )
    await chartinfo.send(msg)


@scoreinfo.handle()
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

    songList = await get_music_data_df()
    result, song_info = await get_info_by_name(song, music_type, songList)
    if result == 1:
        if isinstance(song_info, set):
            msg = f"迪拉熊找到了这些乐曲——\r\n{'\r\n'.join(song_info)}"
            await scoreinfo.finish(msg)
    elif result == 2:
        await scoreinfo.finish(
            (
                MessageSegment.text("迪拉熊没有找到对得上的乐曲mai~"),
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
    data, status = await get_player_record(qq, song_info["id"])
    if status == 400:
        msg = (
            MessageSegment.text("迪拉熊没有找到你的信息mai~"),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await scoreinfo.finish(msg, at_sender=True)
    if status == 200:
        if not data:
            msg = (
                MessageSegment.text("迪拉熊没有找到对得上的乐曲mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            )
            await scoreinfo.finish(msg, at_sender=True)
        records = data[song_info["id"]]
        if not records:
            msg = (
                MessageSegment.text("迪拉熊没有找到你在这首乐曲上的成绩mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            )
            await scoreinfo.finish(msg, at_sender=True)
    elif not data:
        msg = (
            MessageSegment.text("（查分器出了点问题）"),
            MessageSegment.image(Path("./Static/Maimai/Function/2.png")),
        )
        await scoreinfo.finish(msg, at_sender=True)
    if song_info["basic_info"]["genre"] == "宴会場":
        img = await utage_score_info(data, song_info)
    else:
        img = await score_info(data, song_info)
    msg = MessageSegment.image(img)
    await scoreinfo.send(msg, at_sender=True)


@achvinfo.handle()
async def _(event: MessageEvent):
    msg = event.get_plaintext()
    pattern = r"(?:achv|分数表格?)\s*(?:(绿|黄|红|紫|白)\s*(?:(dx|sd|标准?)\s*)?|(?:([左右])\s*)?)(.+)"
    match = re.fullmatch(pattern, msg, re.I)
    song = match.group(4)
    if not song:
        return

    diff = match.group(1)
    type_index = 0
    if diff:
        type_index = "绿黄红紫白".index(diff)
        music_type = match.group(2)
    else:
        music_type = "宴"

    side = match.group(3)
    if side:
        type_index = "左右".index(side)

    songList = await get_music_data_df()
    result, song_info = await get_info_by_name(song, music_type, songList)
    if result == 1:
        if isinstance(song_info, set):
            msg = f"迪拉熊找到了这些乐曲——\r\n{'\r\n'.join(song_info)}"
            await achvinfo.finish(msg)
    elif result == 2:
        await achvinfo.finish(
            (
                MessageSegment.text("迪拉熊没有找到对得上的乐曲mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    elif result == 3:
        await achvinfo.finish(
            (
                MessageSegment.text("结果太多啦，缩小范围再试试吧~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    if diff and song_info["basic_info"]["genre"] == "宴会場":
        await achvinfo.finish(
            (
                MessageSegment.text("迪拉熊没有找到对得上的乐曲mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    chart_count = len(song_info["charts"])
    if chart_count <= type_index:
        await achvinfo.finish(
            (
                MessageSegment.text("迪拉熊没有找到对得上的乐曲mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    if side and chart_count < 2:
        await achvinfo.finish(
            (
                MessageSegment.text("迪拉熊没有找到对得上的乐曲mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    if not diff and not side and chart_count > 1:
        await achvinfo.finish(
            (
                MessageSegment.text("你没有告诉迪拉熊是哪一边的谱面mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    img = await achv_info(song_data=song_info, index=type_index)
    msg = MessageSegment.image(img)
    await achvinfo.send(msg)


@songreq.handle()
async def _(event: MessageEvent):
    msg = event.get_plaintext()
    match = re.fullmatch(r"(?:迪拉熊|dlx)?点歌\s*(.+)", msg, re.I)
    if not match:
        return

    song = match.group(1)
    if not song:
        return

    songList = await get_music_data_df()
    result, song_info = await get_info_by_name(song, None, songList)
    if result == 1:
        if isinstance(song_info, set):
            msg = f"迪拉熊找到了这些乐曲——\r\n{'\r\n'.join(song_info)}"
            await songreq.finish(msg)
    elif result == 2:
        await songreq.finish(
            (
                MessageSegment.text("迪拉熊没有找到对得上的乐曲mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    elif result == 3:
        await songreq.finish(
            (
                MessageSegment.text("结果太多啦，缩小范围再试试吧~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )

    song_id = int(song_info["id"]) % 10000
    await songreq.send(
        MessageSegment.music_custom(
            url=f"https://maimai.lxns.net/songs?game=maimai&song_id={song_id}",
            audio=f"https://assets2.lxns.net/maimai/music/{song_id}.mp3",
            title=song_info["title"],
            content=song_info["basic_info"]["artist"],
            img_url=f"https://assets2.lxns.net/maimai/jacket/{song_id}.png",
        )
    )


@randsong.handle()
async def _(event: MessageEvent):
    rng = random.default_rng()
    msg = event.get_plaintext()
    pattern = r"(绿|黄|红|紫|白)?\s*((?:\d+)(?:\.\d|\+)?)"
    match = re.search(pattern, msg)
    level_label = match.group(1)
    if level_label:
        level_index = "绿黄红紫白".index(level_label)
    else:
        level_index = None
    level = match.group(2)
    s_type = "level"
    if "." in level:
        s_type = "ds"
    s_songs = list()
    songList = await get_music_data_df()
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
        msg = (
            MessageSegment.text("迪拉熊没有找到对得上的乐曲mai~"),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await randsong.finish(msg, at_sender=True)
    song = rng.choice(s_songs)
    img = await chart_info(song_data=song)
    msg = (
        MessageSegment.text(f"{song['id']}：{song['title']}"),
        MessageSegment.image(img),
    )
    await randsong.send(msg)


@maiwhat.handle()
async def _(event: MessageEvent):
    rng = random.default_rng()
    songList = await get_music_data_df()
    song = rng.choice(songList)
    if song["basic_info"]["genre"] == "宴会場":
        img = await utage_chart_info(song_data=song)
    else:
        img = await chart_info(song_data=song)
    msg = (
        MessageSegment.text(f"{song['id']}：{song['title']}"),
        MessageSegment.image(img),
    )
    await maiwhat.send(msg)


# 查看别名
@alias_search.handle()
async def _(event: MessageEvent):
    msg = event.get_plaintext()
    match = re.fullmatch(
        r"(?:alias|查看?别(?:名|称))\s*(.+)|(.+)有(?:什么|哪些)别(?:名|称)？?",
        msg,
        re.I,
    )
    if not match:
        return

    name = match.group(1) or match.group(2)
    if not name:
        await alias_search.finish(
            (
                MessageSegment.text("迪拉熊没有找到对得上的乐曲mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )

    songList = await get_music_data_df()
    result, song_info = await get_info_by_name(name, None, songList)
    if result == 1:
        if isinstance(song_info, set):
            msg = f"迪拉熊找到了这些乐曲——\r\n{'\r\n'.join(song_info)}"
            await alias_search.finish(msg)
    elif result == 2:
        await alias_search.finish(
            (
                MessageSegment.text("迪拉熊没有找到对得上的乐曲mai~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            ),
            at_sender=True,
        )
    elif result == 3:
        await alias_search.finish(
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
            MessageSegment.text("迪拉熊没有找到这首歌的别名mai~"),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await alias_search.send(msg, at_sender=True)
    else:
        song_alias = "\r\n".join(sorted(alias))
        msg = (
            "迪拉熊找到了这些别名——\r\n"
            f"{song_alias}\r\n"
            "\r\n"
            "感谢落雪查分器、X-ray Bot及YuzuChaN Bot提供数据支持"
        )
        await alias_search.send(msg)


@all_frame.handle()
async def _():
    path = "./Static/maimai/allFrame.png"
    await all_frame.send(MessageSegment.image(Path(path)))


@all_plate.handle()
async def _():
    path = "./Static/maimai/allPlate.png"
    await all_plate.send(MessageSegment.image(Path(path)))


@all_icon.handle()
async def _():
    path = "./Static/maimai/allIcon.png"
    await all_icon.send(MessageSegment.image(Path(path)))


@set_plate.handle()
async def _(event: MessageEvent):
    qq = event.get_user_id()
    msg = event.get_plaintext()
    match = re.search(r"\d+", msg)
    id = match.group().lstrip("0")
    try:
        plate = await get_plate(id)
    except HTTPError:
        msg = (
            MessageSegment.text("迪拉熊没有找到合适的姓名框mai~"),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await set_plate.finish(msg, at_sender=True)

    await user_config_manager.set_config_value(qq, "plate", id)
    img_byte_arr = BytesIO()
    plate = plate.convert("RGB")
    plate.save(img_byte_arr, format="JPEG")
    img_byte_arr.seek(0)
    img_bytes = img_byte_arr.getvalue()
    msg = (
        MessageSegment.text("迪拉熊帮你把姓名框换成了——"),
        MessageSegment.image(img_bytes),
    )
    await set_plate.send(msg, at_sender=True)


@set_frame.handle()
async def _(event: MessageEvent):
    qq = event.get_user_id()
    msg = event.get_plaintext()
    match = re.search(r"\d+", msg)
    id = match.group().lstrip("0")
    try:
        frame = await get_frame(id)
    except HTTPError:
        msg = (
            MessageSegment.text("迪拉熊没有找到合适的背景mai~"),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await set_frame.finish(msg, at_sender=True)

    await user_config_manager.set_config_value(qq, "frame", id)
    img_byte_arr = BytesIO()
    frame = frame.convert("RGB")
    frame.save(img_byte_arr, format="JPEG")
    img_byte_arr.seek(0)
    img_bytes = img_byte_arr.getvalue()
    msg = (
        MessageSegment.text("迪拉熊帮你把背景换成了——"),
        MessageSegment.image(img_bytes),
    )
    await set_frame.send(msg, at_sender=True)


@set_icon.handle()
async def _(event: MessageEvent):
    qq = event.get_user_id()
    msg = event.get_plaintext()
    match = re.search(r"\d+", msg)
    id = match.group().lstrip("0")
    try:
        icon = await get_icon(id)
    except HTTPError:
        msg = (
            MessageSegment.text("迪拉熊没有找到合适的头像mai~"),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )
        await set_icon.finish(msg, at_sender=True)

    await user_config_manager.set_config_value(qq, "icon", id)
    img_byte_arr = BytesIO()
    icon = icon.convert("RGB")
    icon.save(img_byte_arr, format="JPEG")
    img_byte_arr.seek(0)
    img_bytes = img_byte_arr.getvalue()
    msg = (
        MessageSegment.text("迪拉熊帮你把头像换成了——"),
        MessageSegment.image(img_bytes),
    )
    await set_icon.send(msg, at_sender=True)


@rasug_on.handle()
async def _(event: MessageEvent):
    qq = event.get_user_id()
    await user_config_manager.set_config_value(qq, "rating_tj", True)
    msg = "迪拉熊帮你换好啦~"
    await rasug_on.send(msg, at_sender=True)


@rasug_off.handle()
async def _(event: MessageEvent):
    qq = event.get_user_id()
    await user_config_manager.set_config_value(qq, "rating_tj", False)
    msg = "迪拉熊帮你换好啦~"
    await rasug_off.send(msg, at_sender=True)


@allow_other_on.handle()
async def _(event: MessageEvent):
    qq = event.get_user_id()
    await user_config_manager.set_config_value(qq, "allow_other", True)
    msg = "迪拉熊帮你换好啦~"
    await allow_other_on.send(msg, at_sender=True)


@allow_other_off.handle()
async def _(event: MessageEvent):
    qq = event.get_user_id()
    await user_config_manager.set_config_value(qq, "allow_other", False)
    msg = "迪拉熊帮你换好啦~"
    await allow_other_off.send(msg, at_sender=True)


@set_source.handle()
async def _(event: MessageEvent):
    qq = event.get_user_id()
    msg = event.get_plaintext()
    if "落雪" in msg:
        source = "lxns"
    elif "水鱼" in msg:
        source = "diving-fish"

    if await user_config_manager.set_config_value(qq, "source", source):
        msg = "迪拉熊帮你换好啦~"
    else:
        msg = (
            MessageSegment.text("你已经在使用这个查分器了mai~"),
            MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
        )

    await set_source.send(msg, at_sender=True)


@set_token.handle()
async def _(event: MessageEvent):
    qq = event.get_user_id()
    match = re.fullmatch(
        r"(?:迪拉熊|dlx)?(?:绑定|bind)\s*(落雪|水鱼)\s*(.+)",
        event.get_plaintext(),
        re.I,
    )
    if not match:
        return

    prober = match.group(1)
    token = match.group(2)
    if prober == "落雪":
        if len(token) != 44:
            msg = (
                MessageSegment.text("你的令牌好像不太对mai~再试一下吧~"),
                MessageSegment.image(Path("./Static/Maimai/Function/1.png")),
            )
            await set_token.finish(msg, at_sender=True)

        await user_config_manager.set_config_value(qq, "lx_personal_token", token)
        msg = "迪拉熊帮你绑好啦~"
    else:
        return

    await set_token.send(msg, at_sender=True)
