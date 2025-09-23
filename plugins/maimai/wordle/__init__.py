import asyncio
import math
import os
import re
from io import BytesIO
from pathlib import Path

import aiofiles
import numpy as np
import soundfile
from PIL import Image
from httpx import AsyncClient
from nonebot import on_message, on_regex
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageSegment
from rapidfuzz import fuzz, process

from util.data import (
    get_alias_list_lxns,
    get_alias_list_xray,
    get_alias_list_ycn,
    get_music_data_lxns,
)
from util.stars import stars
from .database import openchars
from .ranking import ranking
from .times import times
from .utils import (
    check_music_id,
    generate_message_state,
    generate_success_state,
    get_version_name,
)

start_open_chars = on_regex(r"^(迪拉熊|dlx)(猜歌|开字母|k(zm)?)$", re.I)
open_chars = on_regex(r"^开\s*(.|[a-zA-Z]+)$")
all_message_handle = on_message(priority=1000, block=False)
pass_game = on_regex(r"^(结束(猜歌|开字母)|将大局逆转吧)$")
info_tip = on_regex(r"^(提示|提醒|信息)\s*[1-5]?$")
pic_tip = on_regex(r"^(封面|曲绘|图片?)\s*[1-5]?$")
aud_tip = on_regex(r"^(音(乐|频)|(乐|歌)曲|片段)\s*[1-5]?$")
rank = on_regex(r"^(迪拉熊|dlx)(猜歌|开字母|k(zm)?)(排行榜?|榜|rank)$", re.I)
rankth = on_regex(r"^(迪拉熊|dlx)(猜歌|开字母|k(zm)?)((个人)?排名|th)$", re.I)


# 根据乐曲别名查询乐曲id列表
async def find_songid_by_alias(name, song_list):
    # 芝士id列表
    matched_ids = list()

    # 芝士查找
    for info in song_list["songs"]:
        if (
            name.casefold() == info["title"].casefold()
            or (len(info["difficulties"]["standard"]) > 0 and name == str(info["id"]))
            or (len(info["difficulties"]["dx"]) > 0 and name == str(10000 + info["id"]))
        ):
            matched_ids.append(info["id"])

    if matched_ids:
        return matched_ids

    alias_map = dict()

    async def process_lxns(alias_map: dict[str, list[int]]):
        alias_list = await get_alias_list_lxns()
        for info in alias_list["aliases"]:
            song_id = info["song_id"]
            for alias in info["aliases"]:
                alias_map.setdefault(alias, list())
                if song_id in alias_map[alias]:
                    continue
                alias_map[alias].append(song_id)

    async def process_xray(alias_map: dict[str, list[int]]):
        alias_list = await get_alias_list_xray()
        for song_id, info in alias_list.items():
            if len(song_id) == 5:
                song_id = song_id[-4:]
            song_id = int(song_id)
            for alias in info:
                alias_map.setdefault(alias, list())
                if song_id in alias_map[alias]:
                    continue
                alias_map[alias].append(song_id)

    async def process_ycn(alias_map: dict[str, list[int]]):
        alias_list = await get_alias_list_ycn()
        for info in alias_list["content"]:
            if 10000 < info["SongID"] < 20000:
                song_id = info["SongID"] % 10000
            else:
                song_id = info["SongID"]
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


@start_open_chars.handle()
async def _(event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = event.get_user_id()
    await openchars.start(group_id)
    _, game_state, _ = await generate_message_state(group_id, user_id, event.time)

    await start_open_chars.send(
        "要开始了哟~\r\n"
        "\r\n"
        "□——字母或数字\r\n"
        "◎——假名或汉字\r\n"
        "◇——符号\r\n"
        "\r\n"
        "发送“开[文字]”开出字母\r\n"
        "发送“[歌名/别名]”尝试猜歌\r\n"
        "发送“提示（序号）”获取提示（每首5次机会）\r\n"
        "发送“封面（序号）”获取部分封面（每首2次机会）\r\n"
        "发送“歌曲（序号）”获取1秒歌曲片段（每首1次机会）\r\n"
        "发送“结束猜歌”结束\r\n"
        "\r\n"
        "12个小时内没人猜歌，迪拉熊会帮大家结束游戏哦~不用谢mai~（骄傲）"
    )
    await start_open_chars.send(game_state)


@open_chars.handle()
async def _(event: GroupMessageEvent):
    group_id = str(event.group_id)
    user_id = event.get_user_id()
    msg = event.get_plaintext()
    match = re.fullmatch(r"开\s*(.+)", msg)
    if not match:
        return

    char = match.group(1)
    not_opened, game_data = await openchars.open_char(group_id, char, user_id)
    if game_data is None:
        return

    if not not_opened:
        await open_chars.finish(
            (
                MessageSegment.text("这个字已经开过了mai~换一个吧~"),
                MessageSegment.image(Path("./Static/Wordle/1.png")),
            ),
            at_sender=True,
        )

    is_game_over, game_state, char_all_open = await generate_message_state(
        group_id, user_id, event.time
    )
    if char_all_open:
        for i, title, id in char_all_open:
            song_id = id % 10000
            await open_chars.send(f"猜对啦~🎉第{i}首歌是——", at_sender=True)
            await open_chars.send(
                MessageSegment.music_custom(
                    url=f"https://maimai.lxns.net/songs?game=maimai&song_id={song_id}",
                    audio=f"https://assets2.lxns.net/maimai/music/{song_id}.mp3",
                    title=title,
                    content="来自迪拉熊Bot",
                    img_url=f"https://assets2.lxns.net/maimai/jacket/{song_id}.png",
                )
            )

            star, method, extend = await stars.give_rewards(
                user_id, 15, 35, "开字母猜中歌曲", event.time
            )
            msg = f"迪拉熊奖励你{star}颗★mai~"
            if method == 0b0000_0001:
                msg += f"人品大爆发，迪拉熊额外送你{extend}颗★哦~"
            if method & 0b0001_0000:
                msg += f"今日首次奖励，迪拉熊额外送你{extend}颗★哦~"
            await open_chars.send(msg, at_sender=True)

    await open_chars.send(game_state)
    if is_game_over:
        await openchars.game_over(group_id)
        await open_chars.send("全部答对啦，恭喜mai~🎉")


@all_message_handle.handle()
async def _(event: GroupMessageEvent):
    msg_content = event.get_plaintext()
    if not msg_content:
        return

    group_id = str(event.group_id)
    if not await openchars.is_gaming(group_id):
        return

    songList = await get_music_data_lxns()
    music_ids = await find_songid_by_alias(msg_content, songList)
    if not music_ids:
        return

    user_id = event.get_user_id()
    guess_success = await check_music_id(group_id, music_ids, user_id, event.time)
    if not guess_success:
        return

    for i, title, id in guess_success:
        song_id = id % 10000
        await all_message_handle.send(f"猜对啦~🎉第{i}首歌是——", at_sender=True)
        await all_message_handle.send(
            MessageSegment.music_custom(
                url=f"https://maimai.lxns.net/songs?game=maimai&song_id={song_id}",
                audio=f"https://assets2.lxns.net/maimai/music/{song_id}.mp3",
                title=title,
                content="来自迪拉熊Bot",
                img_url=f"https://assets2.lxns.net/maimai/jacket/{song_id}.png",
            )
        )

        star, method, extend = await stars.give_rewards(
            user_id, 15, 35, "开字母猜中歌曲", event.time
        )
        msg = f"迪拉熊奖励你{star}颗★mai~"
        if method == 0b0000_0001:
            msg += f"人品大爆发，迪拉熊额外送你{extend}颗★哦~"
        if method & 0b0001_0000:
            msg += f"今日首次奖励，迪拉熊额外送你{extend}颗★哦~"
        await all_message_handle.send(msg, at_sender=True)

    is_game_over, game_state, _ = await generate_message_state(
        group_id, user_id, event.time
    )
    await all_message_handle.send(game_state)
    if is_game_over:
        await openchars.game_over(group_id)
        await all_message_handle.send("全部答对啦，恭喜mai~🎉")


@pass_game.handle()
async def _(event: GroupMessageEvent):
    group_id = str(event.group_id)
    if not await openchars.is_gaming(group_id):
        return

    game_state = await generate_success_state(group_id)
    await openchars.game_over(group_id)
    await pass_game.send(game_state)
    await pass_game.send("迪拉熊帮大家揭晓答案啦mai~")


@info_tip.handle()
async def _(event: GroupMessageEvent):
    rng = np.random.default_rng()
    group_id = str(event.group_id)
    user_id = event.get_user_id()
    msg = event.get_plaintext()
    index = re.search(r"\d+", msg)
    game_data = await openchars.get_game_data(group_id)
    if not game_data:
        return

    if index:
        index = int(index.group()) - 1
        data = game_data["game_contents"][index]
    else:
        game_contents = [
            d for d in game_data["game_contents"] if not d["is_correct"] and d["tips"]
        ]
        if not game_contents:
            await info_tip.finish(
                (
                    MessageSegment.text("所有歌的信息提示次数都用完了mai~"),
                    MessageSegment.image(Path("./Static/Wordle/1.png")),
                )
            )

        data = rng.choice(game_contents)

    if data["is_correct"]:
        await info_tip.finish(
            (
                MessageSegment.text(f"第{data['index']}首歌已经猜对了mai~"),
                MessageSegment.image(Path("./Static/Wordle/1.png")),
            )
        )

    songList = await get_music_data_lxns()
    tips = {
        "最高等级": lambda s: sorted(
            (chart for charts in s["difficulties"].values() for chart in charts),
            key=lambda x: x["level_value"],
            reverse=True,
        )[0]["level"],
        "谱师": lambda s: sorted(
            (chart for charts in s["difficulties"].values() for chart in charts),
            key=lambda x: x["level_value"],
            reverse=True,
        )[0]["note_designer"],
        "类型": lambda s: "、".join(
            {"dx": "DX", "standard": "标准", "utage": "宴会场"}[k]
            for k in [k for k, v in s["difficulties"].items() if len(v) > 0]
        ),
        "曲师": lambda s: s["artist"],
        "分类": lambda s: [
            genre["title"]
            for genre in songList["genres"]
            if genre["genre"] == s["genre"]
        ][0],
        "BPM": lambda s: s["bpm"],
        "初出版本": lambda s: get_version_name(s["version"], songList),
    }

    tip_keys = [d for d in tips.keys() if d not in data["tips"]]
    if not tip_keys:
        await info_tip.finish(
            (
                MessageSegment.text(f"第{data['index']}首歌信息提示次数已经用完了mai~"),
                MessageSegment.image(Path("./Static/Wordle/1.png")),
            )
        )

    songList = await get_music_data_lxns()
    song = [d for d in songList["songs"] if d["id"] == data["music_id"]]
    if len(song) != 1:
        await info_tip.finish(
            (
                MessageSegment.text(f"第{data['index']}首歌信息提示次数已经用完了mai~"),
                MessageSegment.image(Path("./Static/Wordle/1.png")),
            )
        )

    if user_id not in data["part"]:
        data["part"].append(user_id)
    tip_key = rng.choice(tip_keys)
    data["tips"].append(tip_key)
    await openchars.add_user_to_content_part(group_id, data["index"], user_id)
    await openchars.add_tip_to_content(group_id, data["index"], tip_key)

    tip_info = tips[tip_key](song[0])
    await info_tip.send(f"第{data['index']}首歌的{tip_key}是{tip_info}mai~")


@pic_tip.handle()
async def _(event: GroupMessageEvent):
    rng = np.random.default_rng()
    group_id = str(event.group_id)
    user_id = event.get_user_id()
    msg = event.get_plaintext()
    index = re.search(r"\d+", msg)
    game_data = await openchars.get_game_data(group_id)
    if not game_data:
        return

    if index:
        index = int(index.group()) - 1
        data = game_data["game_contents"][index]
    else:
        game_contents = [
            d
            for d in game_data["game_contents"]
            if not d["is_correct"] and d["pic_times"] < 2
        ]
        if not game_contents:
            await pic_tip.finish(
                (
                    MessageSegment.text("所有歌的封面提示次数都用完了mai~"),
                    MessageSegment.image(Path("./Static/Wordle/1.png")),
                )
            )

        data = rng.choice(game_contents)

    if data["is_correct"]:
        await pic_tip.finish(
            (
                MessageSegment.text(f"第{data['index']}首歌已经猜对了mai~"),
                MessageSegment.image(Path("./Static/Wordle/1.png")),
            )
        )

    if data["pic_times"] >= 2:
        await pic_tip.finish(
            (
                MessageSegment.text(
                    f"第{data['index']}首歌的封面提示次数已经用完了mai~"
                ),
                MessageSegment.image(Path("./Static/Wordle/1.png")),
            )
        )

    if user_id not in data["part"]:
        data["part"].append(user_id)
    data["pic_times"] += 1
    await openchars.add_user_to_content_part(group_id, data["index"], user_id)
    await openchars.increment_content_counter(group_id, data["index"], "pic_times")

    cover_path = f"./Cache/Jacket/{data['music_id'] % 10000}.png"
    if not os.path.exists(cover_path):
        async with AsyncClient(http2=True) as session:
            resp = await session.get(
                f"https://assets2.lxns.net/maimai/jacket/{data['music_id'] % 10000}.png"
            )
            async with aiofiles.open(cover_path, "wb") as fd:
                await fd.write(await resp.aread())

    cover = Image.open(cover_path)
    pers = 1 / math.sqrt(rng.integers(16, 26))
    size_x = math.ceil(cover.height * pers)
    size_y = math.ceil(cover.width * pers)
    pos_x = rng.integers(0, cover.height - size_x, endpoint=True)
    pos_y = rng.integers(0, cover.width - size_y, endpoint=True)
    pice = cover.crop((pos_x, pos_y, pos_x + size_x, pos_y + size_y))
    pice = pice.resize((480, 480))
    img_byte_arr = BytesIO()
    pice = pice.convert("RGB")
    pice.save(img_byte_arr, format="JPEG")
    img_byte_arr.seek(0)
    img_bytes = img_byte_arr.getvalue()
    await pic_tip.send(
        (
            MessageSegment.text(f"第{data['index']}首歌部分封面是——"),
            MessageSegment.image(img_bytes),
        )
    )


@aud_tip.handle()
async def _(event: GroupMessageEvent):
    rng = np.random.default_rng()
    group_id = str(event.group_id)
    user_id = event.get_user_id()
    msg = event.get_plaintext()
    index = re.search(r"\d+", msg)
    game_data = await openchars.get_game_data(group_id)
    if not game_data:
        return

    if index:
        index = int(index.group()) - 1
        data = game_data["game_contents"][index]
    else:
        game_contents = [
            d
            for d in game_data["game_contents"]
            if not d["is_correct"] and d["aud_times"] < 1
        ]
        if not game_contents:
            await aud_tip.finish(
                (
                    MessageSegment.text("所有歌的歌曲提示次数都用完了mai~"),
                    MessageSegment.image(Path("./Static/Wordle/1.png")),
                )
            )

        data = rng.choice(game_contents)

    if data["is_correct"]:
        await aud_tip.finish(
            (
                MessageSegment.text(f"第{data['index']}首歌已经猜对了mai~"),
                MessageSegment.image(Path("./Static/Wordle/1.png")),
            )
        )

    if data["aud_times"] >= 1:
        await aud_tip.finish(
            (
                MessageSegment.text(f"第{data['index']}首歌提示次数已经用完了mai~"),
                MessageSegment.image(Path("./Static/Wordle/1.png")),
            )
        )

    if user_id not in data["part"]:
        data["part"].append(user_id)
    data["aud_times"] += 1
    await openchars.add_user_to_content_part(group_id, data["index"], user_id)
    await openchars.increment_content_counter(group_id, data["index"], "aud_times")

    music_path = f"./Cache/Music/{data['music_id'] % 10000}.mp3"
    if not os.path.exists(music_path):
        async with AsyncClient(http2=True) as session:
            resp = await session.get(
                f"https://assets2.lxns.net/maimai/music/{data['music_id'] % 10000}.mp3"
            )
            async with aiofiles.open(music_path, "wb") as fd:
                await fd.write(await resp.aread())

    audio_data, samplerate = soundfile.read(music_path)
    pos = rng.integers(0, len(audio_data) - samplerate, endpoint=True)
    audio = audio_data[pos : pos + samplerate]
    aud_byte_arr = BytesIO()
    soundfile.write(aud_byte_arr, audio, samplerate, format="MP3")
    aud_byte_arr.seek(0)
    aud_bytes = aud_byte_arr.getvalue()
    await aud_tip.send(MessageSegment.record(aud_bytes))


@rank.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    scores = await ranking.avg_scores()
    leaderboard = [
        (qq, achi, _times)
        for qq, achi, _times in scores
        if await times.check_available(qq)
    ]
    leaderboard_output = list()
    current_score, current_index = 0, 0
    for i, (qq, achi, _times) in enumerate(leaderboard, start=1):
        if achi < current_score or current_score <= 0:
            current_index = i
            current_score = achi

        user_name = (await bot.get_stranger_info(user_id=qq))["nickname"]
        rank_str = f"{current_index}. {user_name}：{math.trunc(achi * 1000000) / 1000000:.4%} × {_times}"
        leaderboard_output.append(rank_str)
        if len(leaderboard_output) > 9:
            break

    avg = np.sum(d[1] for d in scores) / len(scores) if len(scores) > 0 else 0
    msg = "\r\n".join(leaderboard_output)
    msg = (
        "猜歌准确率排行榜前10名是——\r\n"
        f"{msg}\r\n"
        "\r\n"
        f"上榜人数：{len(leaderboard)}/{len(scores)}\r\n"
        f"平均达成率：{math.trunc(avg * 1000000) / 1000000:.4%}\r\n"
        "\r\n"
        "长时间未参与游戏将暂时不会计入排行榜mai~重新结算10次就可以重新上榜啦~"
    )
    await rank.send(msg)


@rankth.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    user_id = event.get_user_id()
    scores = await ranking.avg_scores()
    leaderboard = [
        (qq, achi, _times)
        for qq, achi, _times in scores
        if await times.check_available(qq)
    ]
    leaderboard_output = list()
    index = -1
    for i, (qq, achi, _times) in enumerate(leaderboard):
        if qq == user_id:
            index = i
            break

    if index >= 0:
        leaderboard_output.append("你在排行榜上的位置是——")
        current_score, current_index = leaderboard[0][1], 1
        h_count = 2 if index > 2 else index
        t_count = 2 if len(leaderboard) - index > 2 else len(leaderboard) - index - 1
        pand = h_count + t_count
        s_index = index + 2 - pand
        e_index = index - 2 + pand
        for i, (qq, achi, _times) in enumerate(leaderboard):
            if i > e_index:
                break

            if achi < current_score or current_score <= 0:
                current_index = i + 1
                current_score = achi

            if s_index > i:
                continue

            user_name = (await bot.get_stranger_info(user_id=qq))["nickname"]
            if i == index:
                rank_str = f"> {current_index}. {user_name}：{math.trunc(achi * 1000000) / 1000000:.4%} × {_times}"
            else:
                rank_str = f"{current_index}. {user_name}：{math.trunc(achi * 1000000) / 1000000:.4%} × {_times}"

            leaderboard_output.append(rank_str)
    else:
        leaderboard_output.append("你还没有上榜mai~")
        achi, _times = await ranking.get_score(user_id)
        leaderboard_output.append(
            f"?. {math.trunc(achi * 1000000) / 1000000:.4%} × {_times}"
        )

    msg = "\r\n".join(leaderboard_output)
    msg = (
        f"{msg}\r\n"
        "长时间未参与游戏将暂时不会计入排行榜mai~重新结算10次就可以重新上榜啦~"
    )
    await rankth.send(MessageSegment.text(msg), at_sender=True)
