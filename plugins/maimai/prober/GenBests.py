import math
import os
from io import BytesIO

import aiofiles
import numpy as np
from PIL import Image, ImageFont, ImageDraw
from aiohttp import ClientSession

from util.Config import config as Config
from .Config import (
    font_path,
    maimai_Static,
    maimai_Frame,
    maimai_Dani,
    maimai_Rating,
    maimai_Level,
    maimai_DXScoreStar,
    maimai_MusicType,
    maimai_MusicIcon,
    maimai_Icon,
    maimai_Class,
    maimai_Shougou,
)
from .Draw import paste, text
from .GLOBAL_CONSTANT import version_df_maps, exclude_list

ratings = {
    "app": [1.01, 22.4, 15.0],
    "sssp": [1.005, 22.4, 15.0],
    "sss": [1.0, 21.6, 14.0],
    "ssp": [0.995, 21.1, 13.0],
    "ss": [0.99, 20.8, 12.0],
    "sp": [0.98, 20.3, 11.0],
    "s": [0.97, 20.0, 10.0],
    "aaa": [0.94, 16.8, 9.4],
    "aa": [0.9, 15.2, 9.0],
    "a": [0.8, 13.6, 8.0],
    "bbb": [0.75, 12.0, 7.5],
    "bb": [0.7, 11.2, 7.0],
    "b": [0.6, 9.6, 6.0],
    "c": [0.5, 8.0, 5.0],
    "d": [0.4, 6.4, 4.0],
}

# 字体路径
ttf_black_path = font_path / "rounded-x-mplus-1p-heavy.ttf"
ttf_bold_path = font_path / "rounded-x-mplus-1p-bold.ttf"
ttf_regular_path = font_path / "rounded-x-mplus-1p-medium.ttf"
ttf2_bold_path = font_path / "NotoSansCJKsc-Bold.otf"
ttf2_regular_path = font_path / "NotoSansCJKsc-Regular.otf"


# id查歌
def find_song_by_id(song_id, songList):
    for song in songList:
        if song_id == song["id"]:
            return song

    # 如果没有找到对应 id 的歌曲，返回 None
    return


def resize_image(image, scale):
    # 计算缩放后的目标尺寸
    width = math.ceil(image.width * scale)
    height = math.ceil(image.height * scale)

    # 缩放图像
    resized_image = image.resize((width, height))

    return resized_image


def format_songid(id):
    id_str = str(id)
    if len(id_str) == 5 and id_str.startswith("10"):
        # 五位数且以"10"开头，去掉"10"然后补齐前导零
        return id_str[2:].zfill(6)
    if len(id_str) == 5 and id_str.startswith("1"):
        # 五位数且以"1"开头，去掉"1"然后补齐前导零
        return id_str[1:].zfill(6)
    # 直接补齐前导零至六位
    return id_str.zfill(6)


def compute_record(records: list):
    output = {
        "sssp": 0,
        "sss": 0,
        "ssp": 0,
        "ss": 0,
        "sp": 0,
        "s": 0,
        "clear": 0,
        "app": 0,
        "ap": 0,
        "fcp": 0,
        "fc": 0,
        "fsdp": 0,
        "fsd": 0,
        "fsp": 0,
        "fs": 0,
        "sync": 0,
    }

    for record in records:
        achieve = record["achievements"]
        fc = record["fc"]
        fs = record["fs"]

        if achieve >= 80.0:
            output["clear"] += 1
        if achieve >= 97.0:
            output["s"] += 1
        if achieve >= 98.0:
            output["sp"] += 1
        if achieve >= 99.0:
            output["ss"] += 1
        if achieve >= 99.5:
            output["ssp"] += 1
        if achieve >= 100.0:
            output["sss"] += 1
        if achieve >= 100.5:
            output["sssp"] += 1

        if fc:
            output["fc"] += 1
            if fc == "app":
                output["app"] += 1
                output["ap"] += 1
                output["fcp"] += 1
            if fc == "ap":
                output["ap"] += 1
                output["fcp"] += 1
            if fc == "fcp":
                output["fcp"] += 1
        if fs:
            output["sync"] += 1
            if fs == "fsdp":
                output["fsdp"] += 1
                output["fsd"] += 1
                output["fsp"] += 1
                output["fs"] += 1
            if fs == "fsd":
                output["fsd"] += 1
                output["fsp"] += 1
                output["fs"] += 1
            if fs == "fsp":
                output["fsp"] += 1
                output["fs"] += 1

    return output


def get_min_score(notes: list[int]):
    weight = [1, 2, 3, 1, 5]
    base_score = 5
    sum_score = 0
    for i in range(0, 5):
        if i == 3 and len(notes) < 5:
            sum_score += notes[i] * weight[4] * base_score
            break
        sum_score += notes[i] * weight[i] * base_score
    return (1 - ((sum_score - 1) / sum_score)) * 100


def records_filter(
    records: list,
    level: str | None = None,
    ds: float | None = None,
    gen: str | None = None,
    is_sun: bool = False,
    is_lock: bool = False,
    songList=None,
):
    filted_records = list()
    mask_enabled = False
    for record in records:
        if record["level_label"] == "Utage":
            continue
        if level and record["level"] != level:
            continue
        if ds and record["ds"] != ds:
            continue
        song_data = find_song_by_id(str(record["song_id"]), songList)
        if (
            gen
            and gen in version_df_maps
            and (
                (song_data["basic_info"]["from"] not in version_df_maps[gen])
                or (gen != "舞" and record["level_index"] == 4)
            )
            or (gen in exclude_list and record["song_id"] in exclude_list[gen])
        ):
            continue
        min_score_1 = get_min_score(song_data["charts"][record["level_index"]]["notes"])
        min_score_2 = song_data["charts"][record["level_index"]]["notes"][-1]
        min_score_2 = 1 / min_score_2 / 2 if min_score_2 > 0 else 0
        min_score = min(min_score_1, min_score_2)
        if is_sun:
            if record["dxScore"] == 0:
                mask_enabled = True
                continue
            passed = False
            ra_kv = list(ratings.items())
            ra_k = list(ratings.keys())
            max_acc = ra_kv[ra_k.index(record["rate"]) - 1][1][0] * 100
            min_acc = max_acc - min_score
            if min_acc <= record["achievements"] < max_acc:
                passed = True
            if not passed:
                continue
        if is_lock:
            if record["dxScore"] == 0:
                mask_enabled = True
                continue
            ra_in = ratings[record["rate"]][0]
            min_acc = ra_in * 100
            max_acc = min_acc + min_score
            if max_acc < record["achievements"] or record["achievements"] < min_acc:
                continue
        filted_records.append(record)
    filted_records.sort(
        key=lambda x: (
            0 if level or ds else float(x["level"].replace("+", ".1")),
            x["achievements"],
            x["ra"],
        ),
        reverse=True,
    )
    return filted_records, mask_enabled


def song_list_filter(
    songList, level: str | None = None, ds: float | None = None, gen: str | None = None
):
    count = 0
    for song in songList:
        if song["basic_info"]["genre"] == "宴会場":
            continue
        if level and level in song["level"]:
            count += song["level"].count(level)
        if ds and ds in song["ds"]:
            count += song["level"].count(level)
        if (
            gen
            and song["basic_info"]["from"] in version_df_maps[gen]
            and (gen not in exclude_list or int(song["id"]) not in exclude_list[gen])
        ):
            count += len(song["level"]) if gen == "舞" else 4
    return count


def get_page_records(records, page):
    items_per_page = 55
    start_index = (page - 1) * items_per_page
    end_index = page * items_per_page
    page_data = records[start_index:end_index]
    return page_data


def dxscore_proc(dxscore, sum_dxscore):
    percentage = (dxscore / sum_dxscore) * 100

    if percentage < 85.0:
        return 0, 0
    if percentage < 90.0:
        return 1, 1
    if percentage < 93.0:
        return 1, 2
    if percentage < 95.0:
        return 2, 3
    if percentage < 97.0:
        return 2, 4
    return 3, 5


def rating_proc(ra: int, rate: str):
    try:
        if ra < 232:
            return "-----"

        achieve = ratings[rate][0]
        num = ratings[rate][1]

        result = math.ceil((ra / (achieve * num)) * 10) / 10

        if result > 15.0:
            return "-----"

        return result
    except (KeyError, ZeroDivisionError):
        return "-----"


def compute_ra(ra: int):
    if ra < 999:
        return 1
    if ra < 1999:
        return 2
    if ra < 3999:
        return 3
    if ra < 6999:
        return 4
    if ra < 9999:
        return 5
    if ra < 11999:
        return 6
    if ra < 12999:
        return 7
    if ra < 13999:
        return 8
    if ra < 14499:
        return 9
    if ra < 14999:
        return 10
    return 11


def compute_ra_old(ra: int):
    if ra < 999:
        return 1
    if ra < 1999:
        return 2
    if ra < 2999:
        return 3
    if ra < 3999:
        return 4
    if ra < 4999:
        return 5
    if ra < 5999:
        return 6
    if ra < 6999:
        return 7
    if ra < 7999:
        return 8
    if ra < 8499:
        return 9
    return 11


def get_fit_diff(song_id: str, level_index: int, ds: float, charts) -> float:
    if song_id not in charts["charts"]:
        return ds
    level_data = charts["charts"][song_id][level_index]
    if "fit_diff" not in level_data:
        return ds
    fit_diff = level_data["fit_diff"]
    return fit_diff


async def music_to_part(
    achievements: float,
    ds: float,
    dxScore: int,
    fc: str,
    fs: str,
    level: str,
    level_index: int,
    level_label: str,
    ra: int,
    rate: str,
    song_id: int,
    title: str,
    type: str,
    index: int,
    b_type: str,
    songList,
    cid=0,
    s_ra=0,
    diff=-1,
    preferred=None,
):
    level_label = level_label.replace(":", "")
    color = (255, 255, 255)
    if level_index == 4:
        color = (88, 140, 204)

    # 根据难度 底图
    partbase_path = f"Static/Maimai/Bests/Part/{level_label}.png"
    partbase = Image.open(partbase_path)

    # 歌曲封面
    jacket_path = f"./Cache/Jacket/{song_id % 10000}.png"
    if not os.path.exists(jacket_path):
        async with ClientSession(conn_timeout=3) as session:
            async with session.get(
                f"https://assets2.lxns.net/maimai/jacket/{song_id % 10000}.png"
            ) as resp:
                async with aiofiles.open(jacket_path, "wb") as fd:
                    await fd.write(await resp.read())
    jacket = Image.open(jacket_path)
    jacket = resize_image(jacket, 0.56)
    partbase = paste(partbase, jacket, (36, 41))

    # 歌曲分类 DX / SD
    icon_path = maimai_MusicType / f"{type}.png"
    icon = Image.open(icon_path)
    icon = resize_image(icon, 0.82)
    partbase = paste(partbase, icon, (797, 16))
    draw = ImageDraw.Draw(partbase)

    # 歌名
    ttf = ImageFont.truetype(ttf_bold_path, size=40)
    text_position = (295, 10)
    max_width = 450
    ellipsis = "…"

    # 检查文本的宽度是否超过最大宽度
    if ttf.getlength(title) <= max_width:
        # 文本未超过最大宽度，直接绘制
        draw.text(text_position, title, font=ttf, fill=color)
    else:
        # 文本超过最大宽度，截断并添加省略符号
        truncated_title = title
        while (
            ttf.getlength(f"{truncated_title}{ellipsis}") > max_width
            and len(truncated_title) > 0
        ):
            truncated_title = truncated_title[:-1].strip()
        draw.text(text_position, f"{truncated_title}{ellipsis}", font=ttf, fill=color)

    # 达成率
    ttf = ImageFont.truetype(ttf_black_path, size=76)
    if "." not in str(achievements):
        achievements = f"{achievements}.0"
    achievements = str(achievements).split(".")
    achievements1 = f"{achievements[0]}."
    achievements2 = achievements[1].ljust(4, "0")[:4]
    text_position = (375, 155)
    text_content = str(achievements1)
    draw.text(text_position, text_content, font=ttf, fill=color, anchor="ls")
    text_position = (text_position[0] + ttf.getlength(text_content), 155)
    ttf = ImageFont.truetype(ttf_black_path, size=54)
    text_content = str(achievements2)
    draw.text(text_position, text_content, font=ttf, fill=color, anchor="ls")
    text_position = (text_position[0] + ttf.getlength(text_content), 155)
    ttf = ImageFont.truetype(ttf_black_path, size=65)
    text_content = "%"
    draw.text(text_position, text_content, font=ttf, fill=color, anchor="ls")

    # 一些信息
    # best序号
    ttf1 = ImageFont.truetype(ttf_bold_path, size=24)
    text_position = (336, 270)
    text_content1 = "#"
    text_len = ttf1.getlength(text_content1)
    ttf2 = ImageFont.truetype(ttf_bold_path, size=30)
    text_content2 = str(index)
    xdiff = (text_len + ttf2.getlength(text_content2)) / 2
    text_position = (math.ceil(text_position[0] - xdiff), 270)
    draw.text(
        text_position, text_content1, font=ttf1, fill=(255, 255, 255), anchor="ls"
    )
    text_position = (math.ceil(text_position[0] + text_len), 270)
    draw.text(
        text_position, text_content2, font=ttf2, fill=(255, 255, 255), anchor="ls"
    )
    # 定数和ra
    ds_str = str(ds)
    if b_type == "fit50":
        ds_str = f"{math.trunc(ds * 100) / 100:.2f}"
        ttf = ImageFont.truetype(ttf_bold_path, size=24)
        draw.text(
            (376, 172),
            f"{'+' if diff > 0 else '±' if diff == 0 else ''}{math.trunc(diff * 100) / 100:.2f}",
            font=ttf,
            fill=color,
            anchor="lm",
        )
    elif b_type == "sd50":
        ttf = ImageFont.truetype(ttf_bold_path, size=24)
        draw.text(
            (376, 172),
            f"±{math.trunc(diff * 100) / 100:.2f}",
            font=ttf,
            fill=color,
            anchor="lm",
        )
    s_ra_str = str(song_id)
    s_ra_str2 = "ID"
    ttf = ImageFont.truetype(ttf_bold_path, size=34)
    ds_str = str(ds_str).split(".")
    text_position = (376, 215)
    text_content = f"{ds_str[0]}."
    draw.text(text_position, text_content, font=ttf, fill=color, anchor="ls")
    text_position = (text_position[0] + ttf.getlength(text_content), 215)
    ttf = ImageFont.truetype(ttf_bold_path, size=28)
    text_content = str(ds_str[1])
    draw.text(text_position, text_content, font=ttf, fill=color, anchor="ls")
    ttf = ImageFont.truetype(ttf_bold_path, size=30)
    text_position = (388, 270)
    draw.text(text_position, s_ra_str, font=ttf, fill=(28, 43, 120), anchor="ls")
    text_position = (text_position[0] + ttf.getlength(s_ra_str), 272)
    ttf = ImageFont.truetype(ttf_bold_path, size=24)
    draw.text(text_position, s_ra_str2, font=ttf, fill=(28, 43, 120), anchor="ls")

    ttf = ImageFont.truetype(ttf_bold_path, size=34)
    draw.text((550, 202), str(ra), font=ttf, fill=color, anchor="rm")
    if b_type == "cf50":
        ttf = ImageFont.truetype(ttf_bold_path, size=20)
        draw.text(
            (550, 172),
            f"{'+' if diff > 0 else '±' if diff == 0 else ''}{diff}",
            font=ttf,
            fill=color,
            anchor="rm",
        )
    # dx分数和星星
    ttf = ImageFont.truetype(ttf_bold_path, size=24)
    text_position = (730, 270)
    id_str = str(song_id)
    song_data = [d for d in songList if d["id"] == id_str][0]
    sum_dxscore = np.sum(song_data["charts"][level_index]["notes"]) * 3
    text_content = str(sum_dxscore)
    draw.text(text_position, text_content, font=ttf, fill=(28, 43, 120), anchor="rs")
    if dxScore > 0:
        text_position = (text_position[0] - ttf.getlength(text_content), 270)
        ttf = ImageFont.truetype(ttf_bold_path, size=30)
        text_content = f"{dxScore}/"
        draw.text(
            text_position, text_content, font=ttf, fill=(28, 43, 120), anchor="rs"
        )

    star_level, stars = (
        dxscore_proc(dxScore, sum_dxscore) if sum_dxscore > 0 else (0, 0)
    )
    if star_level:
        star_width = 30
        star_path = maimai_DXScoreStar / f"{star_level}.png"
        star = Image.open(star_path)
        star = resize_image(star, 1.3)
        for i in range(stars):
            x_offset = i * star_width
            partbase = paste(partbase, star, (x_offset + 570, 178))

    # 评价
    rate_path = f"./Static/Maimai/Rate/{rate}.png"
    rate = Image.open(rate_path)
    rate = resize_image(rate, 0.87)
    partbase = paste(partbase, rate, (770, 72))

    # fc ap
    if fc:
        fc_path = maimai_MusicIcon / f"{fc}.png"
        fc = Image.open(fc_path)
        fc = resize_image(fc, 76 / 61)
        partbase = paste(partbase, fc, (781, 191))
    if fs:
        fs_path = maimai_MusicIcon / f"{fs}.png"
        fs = Image.open(fs_path)
        fs = resize_image(fs, 76 / 61)
        partbase = paste(partbase, fs, (875, 191))

    partbase = partbase.resize((340, 110))
    return partbase


async def draw_best(bests: list, type: str, songList, begin: int = 0):
    index = 0
    # 计算列数
    count = len(bests)
    queue_nums = 1 if count < 4 else 1 + math.ceil((count - 3) / 4)
    # 初始化行列标号
    queue_index = 0
    row_index = 0
    # 初始化坐标
    x = 350
    y = 0
    # 初始化底图
    base = Image.new(
        "RGBA", (1440, queue_nums * 110 + (queue_nums - 1) * 10), (0, 0, 0, 0)
    )

    # 通过循环构建列表并传入数据
    # 遍历列表中的选项
    # 循环生成列
    while queue_index < queue_nums:
        # 设置每行的列数
        if queue_index == 0:
            max_row_index = 3  # 第一行3个
        else:
            max_row_index = 4  # 其他行4个

        # 循环生成行
        while row_index < max_row_index:
            if index < count:
                # 根据索引从列表中抽取数据
                song_data = bests[index]
                if type == "fit50":
                    song_data["diff"] = song_data["ds"] - song_data["s_ra"]
                elif type == "cf50":
                    song_data["diff"] = song_data["ra"] - song_data["s_ra"]
                # 传入数据生成图片
                part = await music_to_part(
                    **song_data,
                    index=index + 1 + begin,
                    b_type=type,
                    songList=songList,
                )
                # 将图片粘贴到底图上
                base = paste(base, part, (x, y))
            else:
                break

            # 增加x坐标，序列自增
            x += 350
            row_index += 1
            index += 1

        # 重置x坐标，增加y坐标
        x = 0
        y += 120
        row_index = 0
        queue_index += 1

    return base


def rating_tj(b35max, b35min, b15max, b15min):
    rng = np.random.default_rng()
    ratingbase_path = maimai_Static / "rating_base.png"
    ratingbase = Image.open(ratingbase_path)
    draw = ImageDraw.Draw(ratingbase)
    ttf = ImageFont.truetype(ttf_bold_path, size=30)

    b35max_diff = b35max - b35min
    b35min_diff = rng.integers(1, 6)
    b15max_diff = b15max - b15min
    b15min_diff = rng.integers(1, 6)

    draw.text((155, 64), font=ttf, text=f"+{str(b35max_diff)}", fill=(255, 255, 255))
    draw.text((155, 104), font=ttf, text=f"+{str(b35min_diff)}", fill=(255, 255, 255))
    draw.text((155, 170), font=ttf, text=f"+{str(b15max_diff)}", fill=(255, 255, 255))
    draw.text((155, 210), font=ttf, text=f"+{str(b15min_diff)}", fill=(255, 255, 255))

    b35max_ra_sssp = rating_proc(b35max, "sssp")
    b35min_ra_sssp = rating_proc((b35min + b35min_diff), "sssp")
    b15max_ra_sssp = rating_proc(b15max, "sssp")
    b15min_ra_sssp = rating_proc((b15min + b15min_diff), "sssp")
    draw.text((270, 64), font=ttf, text=str(b35max_ra_sssp), fill=(255, 255, 255))
    draw.text((270, 104), font=ttf, text=str(b35min_ra_sssp), fill=(255, 255, 255))
    draw.text((270, 170), font=ttf, text=str(b15max_ra_sssp), fill=(255, 255, 255))
    draw.text((270, 210), font=ttf, text=str(b15min_ra_sssp), fill=(255, 255, 255))

    b35max_ra_sss = rating_proc(b35max, "sss")
    b35min_ra_sss = rating_proc((b35min + b35min_diff), "sss")
    b15max_ra_sss = rating_proc(b15max, "sss")
    b15min_ra_sss = rating_proc((b15min + b15min_diff), "sss")
    draw.text((390, 64), font=ttf, text=str(b35max_ra_sss), fill=(255, 255, 255))
    draw.text((390, 104), font=ttf, text=str(b35min_ra_sss), fill=(255, 255, 255))
    draw.text((390, 170), font=ttf, text=str(b15max_ra_sss), fill=(255, 255, 255))
    draw.text((390, 210), font=ttf, text=str(b15min_ra_sss), fill=(255, 255, 255))

    b35max_ra_ssp = rating_proc(b35max, "ssp")
    b35min_ra_ssp = rating_proc((b35min + b35min_diff), "ssp")
    b15max_ra_ssp = rating_proc(b15max, "ssp")
    b15min_ra_ssp = rating_proc((b15min + b15min_diff), "ssp")
    draw.text((510, 64), font=ttf, text=str(b35max_ra_ssp), fill=(255, 255, 255))
    draw.text((510, 104), font=ttf, text=str(b35min_ra_ssp), fill=(255, 255, 255))
    draw.text((510, 170), font=ttf, text=str(b15max_ra_ssp), fill=(255, 255, 255))
    draw.text((510, 210), font=ttf, text=str(b15min_ra_ssp), fill=(255, 255, 255))

    b35max_ra_ss = rating_proc(b35max, "ss")
    b35min_ra_ss = rating_proc((b35min + b35min_diff), "ss")
    b15max_ra_ss = rating_proc(b15max, "ss")
    b15min_ra_ss = rating_proc((b15min + b15min_diff), "ss")
    draw.text((630, 64), font=ttf, text=str(b35max_ra_ss), fill=(255, 255, 255))
    draw.text((630, 104), font=ttf, text=str(b35min_ra_ss), fill=(255, 255, 255))
    draw.text((630, 170), font=ttf, text=str(b15max_ra_ss), fill=(255, 255, 255))
    draw.text((630, 210), font=ttf, text=str(b15min_ra_ss), fill=(255, 255, 255))

    return ratingbase


async def generatebests(
    b35: list,
    b15: list,
    nickname: str,
    dani: int,
    type: str,
    icon: str,
    frame: str,
    plate: str,
    is_rating_tj: bool,
    songList,
):
    b35_ra = np.sum(item["ra"] for item in b35)
    b15_ra = np.sum(item["ra"] for item in b15)
    rating = b35_ra + b15_ra
    if type == "best40":
        rating += 2100

    # BG
    bests = Image.open("./Static/Maimai/Bests/background.png")

    # 底板
    if frame:
        frame_path = maimai_Frame / f"UI_Frame_{frame}.png"
        if not os.path.exists(frame_path):
            async with ClientSession(conn_timeout=3) as session:
                async with session.get(
                    f"https://assets2.lxns.net/maimai/frame/{frame}.png"
                ) as resp:
                    async with aiofiles.open(frame_path, "wb") as fd:
                        await fd.write(await resp.read())
        frame = Image.open(frame_path)
        frame = resize_image(frame, 0.95)
        bests = paste(bests, frame, (48, 45))

    # 牌子
    plate_path = f"./Cache/Plate/{plate}.png"
    if not os.path.exists(plate_path):
        async with ClientSession(conn_timeout=3) as session:
            async with session.get(
                f"https://assets2.lxns.net/maimai/plate/{plate}.png"
            ) as resp:
                async with aiofiles.open(plate_path, "wb") as fd:
                    await fd.write(await resp.read())
    plate = Image.open(plate_path)
    bests = paste(bests, plate, (60, 60))

    # 头像框
    iconbase_path = maimai_Static / "icon_base.png"
    iconbase = Image.open(iconbase_path)
    iconbase = resize_image(iconbase, 0.308)
    bests = paste(bests, iconbase, (60, 46))
    # 头像
    icon_pic_path = maimai_Icon / f"{icon}.png"
    if not os.path.exists(icon_pic_path):
        async with ClientSession(conn_timeout=3) as session:
            async with session.get(
                f"https://assets2.lxns.net/maimai/icon/{icon}.png"
            ) as resp:
                async with aiofiles.open(icon_pic_path, "wb") as fd:
                    await fd.write(await resp.read())
    icon_pic = Image.open(icon_pic_path)
    icon_pic = icon_pic.resize((88, 88))
    bests = paste(bests, icon_pic, (73, 75))

    # 姓名框
    namebase_path = maimai_Static / "namebase.png"
    namebase = Image.open(namebase_path)
    bests = paste(bests, namebase, (0, 0))

    # 段位
    dani_path = maimai_Dani / f"{dani}.png"
    dani = Image.open(dani_path)
    dani = resize_image(dani, 0.213)
    bests = paste(bests, dani, (400, 110))

    # 阶级
    class_path = maimai_Class / "0.png"
    cla = Image.open(class_path)
    cla = resize_image(cla, 0.78)
    bests = paste(bests, cla, (400, 50))

    # rating推荐
    if type == "b50" and is_rating_tj:
        b35max = b35[0]["ra"] if b35 else 0
        b35min = b35[-1]["ra"] if b35 else 0
        b15max = b15[0]["ra"] if b15 else 0
        b15min = b15[-1]["ra"] if b15 else 0
        ratingbase = rating_tj(b35max, b35min, b15max, b15min)
        bests = paste(bests, ratingbase, (60, 197))

    # rating框
    ratingbar = compute_ra_old(rating) if type == "best40" else compute_ra(rating)
    ratingbar_path = maimai_Rating / f"UI_CMN_DXRating_{ratingbar:02d}.png"
    ratingbar = Image.open(ratingbar_path)
    ratingbar = resize_image(ratingbar, 0.26)
    bests = paste(bests, ratingbar, (175, 70))

    # rating数字
    rating_str = str(rating).rjust(5)
    num1 = Image.open(f"./Static/maimai/number/{rating_str[0]}.png").resize((18, 20))
    num2 = Image.open(f"./Static/maimai/number/{rating_str[1]}.png").resize((18, 20))
    num3 = Image.open(f"./Static/maimai/number/{rating_str[2]}.png").resize((18, 20))
    num4 = Image.open(f"./Static/maimai/number/{rating_str[3]}.png").resize((18, 20))
    num5 = Image.open(f"./Static/maimai/number/{rating_str[4]}.png").resize((18, 20))

    bests = paste(bests, num1, (253, 78))
    bests = paste(bests, num2, (267, 78))
    bests = paste(bests, num3, (281, 78))
    bests = paste(bests, num4, (294, 78))
    bests = paste(bests, num5, (308, 78))
    draw = ImageDraw.Draw(bests)

    # 名字
    ttf = ImageFont.truetype(ttf2_regular_path, size=24)
    draw.text((186, 108), nickname, font=ttf, fill=(0, 0, 0))

    # rating合计
    ttf = ImageFont.truetype(ttf2_bold_path, size=14)
    draw.text(
        (334, 154),
        (
            f"Best35：{b35_ra} | Best15：{b15_ra}"
            if type == "all50"
            else (
                f"Best40：{b35_ra + b15_ra} | 段位RATING：2100"
                if type == "best40"
                else f"历史版本：{b35_ra} | 现行版本：{b15_ra}"
            )
        ),
        font=ttf,
        fill=(255, 255, 255),
        anchor="mm",
    )

    frame_path = "./Static/Maimai/Bests/frame.png"
    frame = Image.open(frame_path)
    frame = resize_image(frame, 0.745)
    bests = paste(bests, frame, (40, 36))
    draw = ImageDraw.Draw(bests)

    # 类型
    type_names = {
        "fit50": "Best 拟合难度 50",
        "dxs50": "Best DX分达成率 50（准度b50）",
        "star50": "Best 50（按DX分筛选）",
        "rate50": "Best 50（按评级筛选）",
        "ap50": "全完美 Best 50",
        "fc50": "全连 Best 50",
        "cf50": "对比 Best 50",
        "sd50": "Best 成绩标准差 50（含金量b50）",
        "all50": "全成绩 Best 50",
        "best40": "Best 40",
        "rr50": "",
    }
    type_name = type_names[type] if type in type_names else "Best 50"
    ttf = ImageFont.truetype(ttf2_bold_path, size=32)
    draw.text((720, 740), type_name, font=ttf, fill=(0, 109, 103), anchor="mm")

    # bests
    b35 = await draw_best(b35, type, songList)
    b15 = await draw_best(b15, type, songList)
    bests = paste(bests, b35, (25, 795))
    bests = paste(bests, b15, (25, 1985))

    ttf = ImageFont.truetype(ttf2_regular_path, size=16)
    bests = text(
        text(
            bests,
            xy=(bests.width - 16, bests.height - 32),
            font=ttf,
            text=f"感谢水鱼查分器提供数据支持",
            fill=(0, 0, 0, 50),
            anchor="rb",
        ),
        xy=(bests.width - 16, bests.height - 16),
        font=ttf,
        text=f"Ver.{Config.version[0]}.{Config.version[1]}-{Config.version[2]}",
        fill=(0, 0, 0, 50),
        anchor="rb",
    )

    img_byte_arr = BytesIO()
    bests = bests.convert("RGB")
    bests.save(img_byte_arr, format="JPEG")
    img_byte_arr.seek(0)
    img_bytes = img_byte_arr.getvalue()

    return img_bytes


async def generate_wcb(
    page: int,
    nickname: str,
    dani: int,
    rating: int,
    input_records,
    all_page_num,
    icon: str,
    frame: str,
    plate: str,
    songList,
    level: str | None = None,
    ds: float | None = None,
    gen: str | None = None,
    rate_count=None,
):
    bg = Image.open("./Static/Maimai/List/background.png")

    # 底板
    if level or ds or gen:
        frame_path = "./Static/Maimai/List/frame.png"
    else:
        frame_path = maimai_Frame / f"UI_Frame_{frame}.png"
        if not os.path.exists(frame_path):
            async with ClientSession(conn_timeout=3) as session:
                async with session.get(
                    f"https://assets2.lxns.net/maimai/frame/{frame}.png"
                ) as resp:
                    async with aiofiles.open(frame_path, "wb") as fd:
                        await fd.write(await resp.read())
    frame = Image.open(frame_path)
    frame = resize_image(frame, 0.95)
    bg = paste(bg, frame, (48, 45))

    # 牌子
    plate_path = f"./Cache/Plate/{plate}.png"
    if not os.path.exists(plate_path):
        async with ClientSession(conn_timeout=3) as session:
            async with session.get(
                f"https://assets2.lxns.net/maimai/plate/{plate}.png"
            ) as resp:
                async with aiofiles.open(plate_path, "wb") as fd:
                    await fd.write(await resp.read())
    plate = Image.open(plate_path)
    bg = paste(bg, plate, (60, 60))

    # 头像框
    iconbase_path = maimai_Static / "icon_base.png"
    iconbase = Image.open(iconbase_path)
    iconbase = resize_image(iconbase, 0.308)
    bg = paste(bg, iconbase, (60, 46))
    # 头像
    icon_pic_path = maimai_Icon / f"{icon}.png"
    if not os.path.exists(icon_pic_path):
        async with ClientSession(conn_timeout=3) as session:
            async with session.get(
                f"https://assets2.lxns.net/maimai/icon/{icon}.png"
            ) as resp:
                async with aiofiles.open(icon_pic_path, "wb") as fd:
                    await fd.write(await resp.read())
    icon_pic = Image.open(icon_pic_path)
    icon_pic = icon_pic.resize((88, 88))
    bg = paste(bg, icon_pic, (73, 75))

    # 姓名框
    namebase_path = maimai_Static / "namebase.png"
    namebase = Image.open(namebase_path)
    bg = paste(bg, namebase, (0, 0))

    # 段位
    dani_path = maimai_Dani / f"{dani}.png"
    dani = Image.open(dani_path)
    dani = resize_image(dani, 0.213)
    bg = paste(bg, dani, (400, 110))

    # 阶级
    class_path = maimai_Class / "0.png"
    cla = Image.open(class_path)
    cla = resize_image(cla, 0.78)
    bg = paste(bg, cla, (400, 50))

    # rating框
    ratingbar = compute_ra(rating)
    ratingbar_path = maimai_Rating / f"UI_CMN_DXRating_{ratingbar:02d}.png"
    ratingbar = Image.open(ratingbar_path)
    ratingbar = resize_image(ratingbar, 0.26)
    bg = paste(bg, ratingbar, (175, 70))

    # rating数字
    rating_str = str(rating).rjust(5)
    num1 = Image.open(f"./Static/maimai/number/{rating_str[0]}.png").resize((18, 20))
    num2 = Image.open(f"./Static/maimai/number/{rating_str[1]}.png").resize((18, 20))
    num3 = Image.open(f"./Static/maimai/number/{rating_str[2]}.png").resize((18, 20))
    num4 = Image.open(f"./Static/maimai/number/{rating_str[3]}.png").resize((18, 20))
    num5 = Image.open(f"./Static/maimai/number/{rating_str[4]}.png").resize((18, 20))

    bg = paste(bg, num1, (253, 78))
    bg = paste(bg, num2, (267, 78))
    bg = paste(bg, num3, (281, 78))
    bg = paste(bg, num4, (294, 78))
    bg = paste(bg, num5, (308, 78))
    draw = ImageDraw.Draw(bg)

    # 名字
    ttf = ImageFont.truetype(ttf2_regular_path, size=24)
    draw.text((186, 108), nickname, font=ttf, fill=(0, 0, 0))

    # 称号
    shougou_path = maimai_Shougou / "Normal.png"
    shougou = Image.open(shougou_path)
    shougou = resize_image(shougou, 0.7)
    bg = paste(bg, shougou, (237, 143))
    draw = ImageDraw.Draw(bg)

    if level:
        # 绘制的完成表的等级贴图
        level_icon_path = maimai_Level / f"{level}.png"
        level_icon = Image.open(level_icon_path)
        level_icon = resize_image(level_icon, 0.7)
        bg = paste(bg, level_icon, (755 - (len(level) * 8), 45))
        draw = ImageDraw.Draw(bg)

    if level or ds or gen:
        # 绘制各达成数目
        all_count = song_list_filter(songList, level, ds, gen)
        ttf = ImageFont.truetype(font=ttf_bold_path, size=20)
        rate_list = ["sssp", "sss", "ssp", "ss", "sp", "s", "clear"]
        fcfs_list = ["app", "ap", "fcp", "fc", "fsdp", "fsd", "fsp", "fs"]
        rate_x = 202
        rate_y = 264
        fcfs_x = 203
        fcfs_y = 362
        for rate in rate_list:
            rate_num = rate_count[rate]
            draw.text(
                (rate_x, rate_y),
                f"{rate_num}/{all_count}",
                font=ttf,
                fill=(200, 200, 0) if rate_num == all_count else (53, 74, 164),
                anchor="mm",
            )
            rate_x += 118
        for fcfs in fcfs_list:
            fcfs_num = rate_count[fcfs]
            draw.text(
                (fcfs_x, fcfs_y),
                f"{fcfs_num}/{all_count}",
                font=ttf,
                fill=(200, 200, 0) if fcfs_num == all_count else (53, 74, 164),
                anchor="mm",
            )
            fcfs_x += 102

    frame_path = "./Static/Maimai/Bests/frame.png"
    frame = Image.open(frame_path)
    frame = resize_image(frame, 0.745)
    bg = paste(bg, frame, (40, 36))
    draw = ImageDraw.Draw(bg)

    # 页码
    page_text = f"{page} / {all_page_num}"
    ttf = ImageFont.truetype(font=ttf_black_path, size=70)
    draw.text((260, 850), page_text, font=ttf, fill=(53, 74, 164), anchor="mm")

    # 绘制当前页面的成绩
    records_parts = await draw_best(
        input_records,
        type="wcb",
        begin=(page - 1) * 55,
        songList=songList,
    )
    bg = paste(bg, records_parts, (25, 795))

    ttf = ImageFont.truetype(ttf2_regular_path, size=16)
    bg = text(
        text(
            bg,
            xy=(bg.width - 16, bg.height - 32),
            font=ttf,
            text=f"感谢水鱼查分器提供数据支持",
            fill=(255, 255, 255, 205),
            anchor="rb",
        ),
        xy=(bg.width - 16, bg.height - 16),
        font=ttf,
        text=f"Ver.{Config.version[0]}.{Config.version[1]}-{Config.version[2]}",
        fill=(255, 255, 255, 205),
        anchor="rb",
    )

    img_byte_arr = BytesIO()
    bg = bg.convert("RGB")
    bg.save(img_byte_arr, format="JPEG")
    img_byte_arr.seek(0)
    img_bytes = img_byte_arr.getvalue()

    return img_bytes
