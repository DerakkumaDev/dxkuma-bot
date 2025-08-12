import math
import os
from io import BytesIO

import aiofiles
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from httpx import AsyncClient

from util.Config import config
from util.Data import get_chart_stats
from .Config import (
    font_path,
    maimai_Static,
    maimai_Version,
    maimai_Plus,
    maimai_MusicType,
)
from .Draw import paste, text
from .GenBests import get_fit_diff

# 字体路径
ttf_black_path = font_path / "rounded-x-mplus-1p-heavy.ttf"
ttf_bold_path = font_path / "rounded-x-mplus-1p-bold.ttf"
ttf_regular_path = font_path / "rounded-x-mplus-1p-medium.ttf"
ttf2_bold_path = font_path / "NotoSansCJKsc-Bold.otf"
ttf2_regular_path = font_path / "NotoSansCJKsc-Regular.otf"


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
        # 五位数且以"10"开头,去掉"10"然后补齐前导零
        return id_str[2:].zfill(6)
    if len(id_str) == 5 and id_str.startswith("1"):
        # 五位数且以"1"开头,去掉"1"然后补齐前导零
        return id_str[1:].zfill(6)
    # 直接补齐前导零至六位
    return id_str.zfill(6)


async def music_info(song_data):
    # 底图
    bg = Image.open("./Static/Maimai/Chart/background.png")

    # 歌曲封面
    cover_path = f"./Cache/Jacket/{int(song_data['id']) % 10000}.png"
    if not os.path.exists(cover_path):
        async with AsyncClient(http2=True) as session:
            resp = await session.get(
                f"https://assets2.lxns.net/maimai/jacket/{int(song_data['id']) % 10000}.png"
            )
            async with aiofiles.open(cover_path, "wb") as fd:
                await fd.write(await resp.aread())
    cover = Image.open(cover_path).resize((295, 295))
    bg = paste(bg, cover, (204, 440))
    drawtext = ImageDraw.Draw(bg)

    # 绘制标题
    song_title = song_data["title"]
    ttf = ImageFont.truetype(ttf_bold_path, size=40)
    title_position = (545, 626)
    max_width = 565
    ellipsis = "…"
    # 检查文本的宽度是否超过最大宽度
    if ttf.getlength(song_title) <= max_width:
        # 文本未超过最大宽度,直接绘制
        drawtext.text(title_position, song_title, font=ttf, fill=(0, 0, 0))
    else:
        # 文本超过最大宽度,截断并添加省略符号
        truncated_title = song_title
        while (
            ttf.getlength(f"{truncated_title}{ellipsis}") > max_width
            and len(truncated_title) > 0
        ):
            truncated_title = truncated_title[:-1].strip()
        drawtext.text(
            title_position, f"{truncated_title}{ellipsis}", font=ttf, fill=(0, 0, 0)
        )

    # 绘制曲师
    song_artist = song_data["basic_info"]["artist"]
    ttf = ImageFont.truetype(ttf_regular_path, size=30)
    artist_position = (545, 694)
    max_width = 565
    ellipsis = "…"
    # 检查文本的宽度是否超过最大宽度
    if ttf.getlength(song_artist) <= max_width:
        # 文本未超过最大宽度,直接绘制
        drawtext.text(artist_position, song_artist, font=ttf, fill=(0, 0, 0))
    else:
        # 文本超过最大宽度,截断并添加省略符号
        truncated_title = song_artist
        while (
            ttf.getlength(f"{truncated_title}{ellipsis}") > max_width
            and len(truncated_title) > 0
        ):
            truncated_title = truncated_title[:-1].strip()
        drawtext.text(
            artist_position, f"{truncated_title}{ellipsis}", font=ttf, fill=(0, 0, 0)
        )

    # id
    ttf = ImageFont.truetype(ttf_bold_path, size=28)
    id_position = (239, 872)
    drawtext.text(
        id_position,
        song_data["id"],
        anchor="mm",
        font=ttf,
        fill=(53, 74, 164),
    )
    # bpm
    song_bpm = str(song_data["basic_info"]["bpm"])
    bpm_position = (341, 872)
    drawtext.text(
        bpm_position,
        song_bpm,
        anchor="mm",
        font=ttf,
        fill=(53, 74, 164),
    )
    # 分类
    ttf = ImageFont.truetype(ttf2_bold_path, size=28)
    song_genre = song_data["basic_info"]["genre"]
    genre_position = (544, 872)
    drawtext.text(
        genre_position,
        song_genre,
        anchor="mm",
        font=ttf,
        fill=(53, 74, 164),
    )
    # 谱面类型
    ttf = ImageFont.truetype(ttf_bold_path, size=28)
    song_type = song_data["type"]
    type_path = maimai_MusicType / f"{song_type}.png"
    type = Image.open(type_path)
    type = resize_image(type, 0.7)
    bg = paste(bg, type, (694, 852))
    # version
    song_ver = song_data["basic_info"]["from"]
    song_ver = Image.open(maimai_Version / f"{song_ver}.png")
    song_ver = resize_image(song_ver, 0.8)
    bg = paste(bg, song_ver, (860, 768))
    drawtext = ImageDraw.Draw(bg)

    # 等级
    ttf = ImageFont.truetype(ttf_black_path, size=50)
    songs_level = song_data["level"]
    level_color = [
        (14, 117, 54),
        (214, 148, 19),
        (192, 33, 56),
        (103, 20, 141),
        (186, 126, 232),
    ]
    level_x = 395
    level_y = 1046
    for i, song_level in enumerate(songs_level):
        if "+" in song_level:
            song_level = song_level.replace("+", str())
            level_label = ["Basic", "Advanced", "Expert", "Master", "ReMASTER"][i]
            plus_path = maimai_Plus / f"{level_label}.png"
            plus_icon = Image.open(plus_path)
            bg = paste(bg, plus_icon, (level_x + 33, level_y - 70))
            drawtext = ImageDraw.Draw(bg)
        level_position = (level_x, level_y)
        drawtext.text(
            level_position, song_level, anchor="mm", font=ttf, fill=level_color[i]
        )
        level_x += 170

    # 定数->ra
    ttf = ImageFont.truetype(ttf_bold_path, size=16)
    songs_ds = song_data["ds"]
    ds_x = 395
    ds_y = 1124
    charts = await get_chart_stats()
    for i, song_ds in enumerate(songs_ds):
        ds_position = (ds_x, ds_y)
        drawtext.text(
            ds_position,
            f"{song_ds} ({math.trunc(get_fit_diff(song_data['id'], i, song_ds, charts) * 100) / 100:.2f})",
            anchor="mm",
            font=ttf,
            fill=level_color[i],
        )
        ds_x += 170

    # 物量
    ttf = ImageFont.truetype(ttf_bold_path, size=40)
    song_charts = song_data["charts"]
    notes_x = 395
    for i, chart in enumerate(song_charts):
        notes_y = 1200
        notes = chart["notes"]
        if song_type == "SD":
            notes.insert(3, 0)
        total_num = np.sum(notes)
        dx_num = total_num * 3
        notes.insert(0, total_num)
        notes.append(dx_num)
        for note in notes:
            if note > 0:
                notes_position = (notes_x, notes_y)
                drawtext.text(
                    notes_position,
                    str(note),
                    anchor="mm",
                    font=ttf,
                    fill=level_color[i],
                )
            notes_y += 80
        notes_x += 170

    # 谱师
    ttf = ImageFont.truetype(ttf_regular_path, size=20)
    song_charters = [item["charter"] for item in song_charts[2:]]
    charter_x = 448
    charter_y = 1792
    charter_color = [(192, 33, 56), (103, 20, 141), (186, 126, 232)]
    for i, song_charter in enumerate(song_charters):
        charter_position = (charter_x, charter_y)
        drawtext.text(
            charter_position, song_charter, anchor="mm", font=ttf, fill=charter_color[i]
        )
        charter_x += 292

    ttf = ImageFont.truetype(ttf2_regular_path, size=16)
    bg = text(
        text(
            bg,
            xy=(bg.width - 16, bg.height - 32),
            font=ttf,
            text="感谢水鱼查分器提供数据支持",
            fill=(255, 255, 255, 205),
            anchor="rb",
        ),
        xy=(bg.width - 16, bg.height - 16),
        font=ttf,
        text=f"Ver.{config.version[0]}.{config.version[1]}-{config.version[2]}",
        fill=(255, 255, 255, 205),
        anchor="rb",
    )

    img_byte_arr = BytesIO()
    bg = bg.convert("RGB")
    bg.save(img_byte_arr, format="JPEG")
    img_byte_arr.seek(0)
    img_bytes = img_byte_arr.getvalue()

    return img_bytes


async def play_info(data, song_data):
    records = data[song_data["id"]]
    # 底图
    bg = Image.open("./Static/Maimai/Score/background.png")

    # 歌曲封面
    cover_path = f"./Cache/Jacket/{int(song_data['id']) % 10000}.png"
    if not os.path.exists(cover_path):
        async with AsyncClient(http2=True) as session:
            resp = await session.get(
                f"https://assets2.lxns.net/maimai/jacket/{int(song_data['id']) % 10000}.png"
            )
            async with aiofiles.open(cover_path, "wb") as fd:
                await fd.write(await resp.aread())
    cover = Image.open(cover_path).resize((295, 295))
    bg = paste(bg, cover, (204, 440))
    drawtext = ImageDraw.Draw(bg)

    # 绘制标题
    song_title = song_data["title"]
    ttf = ImageFont.truetype(ttf_bold_path, size=40)
    title_position = (545, 626)
    max_width = 565
    ellipsis = "…"
    # 检查文本的宽度是否超过最大宽度
    if ttf.getlength(song_title) <= max_width:
        # 文本未超过最大宽度,直接绘制
        drawtext.text(title_position, song_title, font=ttf, fill=(0, 0, 0))
    else:
        # 文本超过最大宽度,截断并添加省略符号
        truncated_title = song_title
        while (
            ttf.getlength(f"{truncated_title}{ellipsis}") > max_width
            and len(truncated_title) > 0
        ):
            truncated_title = truncated_title[:-1].strip()
        drawtext.text(
            title_position, truncated_title + ellipsis, font=ttf, fill=(0, 0, 0)
        )

    # 绘制曲师
    song_artist = song_data["basic_info"]["artist"]
    ttf = ImageFont.truetype(ttf_regular_path, size=30)
    artist_position = (545, 694)
    max_width = 565
    ellipsis = "…"
    # 检查文本的宽度是否超过最大宽度
    if ttf.getlength(song_artist) <= max_width:
        # 文本未超过最大宽度,直接绘制
        drawtext.text(artist_position, song_artist, font=ttf, fill=(0, 0, 0))
    else:
        # 文本超过最大宽度,截断并添加省略符号
        truncated_title = song_artist
        while (
            ttf.getlength(f"{truncated_title}{ellipsis}") > max_width
            and len(truncated_title) > 0
        ):
            truncated_title = truncated_title[:-1].strip()
        drawtext.text(
            artist_position, truncated_title + ellipsis, font=ttf, fill=(0, 0, 0)
        )

    # id
    ttf = ImageFont.truetype(ttf_bold_path, size=28)
    id_position = (239, 872)
    drawtext.text(
        id_position,
        song_data["id"],
        anchor="mm",
        font=ttf,
        fill=(53, 74, 164),
    )
    # bpm
    song_bpm = str(song_data["basic_info"]["bpm"])
    bpm_position = (341, 872)
    drawtext.text(
        bpm_position,
        song_bpm,
        anchor="mm",
        font=ttf,
        fill=(53, 74, 164),
    )
    # 分类
    ttf = ImageFont.truetype(ttf2_bold_path, size=28)
    song_genre = song_data["basic_info"]["genre"]
    genre_position = (544, 872)
    drawtext.text(
        genre_position,
        song_genre,
        anchor="mm",
        font=ttf,
        fill=(53, 74, 164),
    )
    # 谱面类型
    ttf = ImageFont.truetype(ttf_bold_path, size=28)
    song_type = song_data["type"]
    type_path = maimai_MusicType / f"{song_type}.png"
    type = Image.open(type_path)
    type = resize_image(type, 0.7)
    bg = paste(bg, type, (694, 852))
    # version
    song_ver = song_data["basic_info"]["from"]
    song_ver = Image.open(maimai_Version / f"{song_ver}.png")
    song_ver = resize_image(song_ver, 0.8)
    bg = paste(bg, song_ver, (860, 760))
    drawtext = ImageDraw.Draw(bg)

    # 绘制成绩
    score_color = [
        (14, 117, 54),
        (214, 148, 19),
        (192, 33, 56),
        (103, 20, 141),
        (186, 126, 232),
    ]
    for i, level in enumerate(song_data["level"]):
        level_x = 229
        level_y = 1100
        achieve_x = 471
        achieve_y = 1102
        rate_x = 646
        rate_y = 1074
        fc_x = 809
        fc_y = 1060
        fs_x = 895
        fs_y = 1060
        dsra_x = 1047
        dsra_y = 1102
        plus_x = 262
        plus_y = 1030

        level_y += i * 150
        achieve_y += i * 150
        rate_y += i * 150
        fc_y += i * 150
        fs_y += i * 150
        dsra_y += i * 150
        plus_y += i * 150

        level_label = ["Basic", "Advanced", "Expert", "Master", "ReMASTER"][i]
        color = score_color[i]

        # 等级
        if "+" in level:
            level = level.replace("+", str())
            plus_path = maimai_Plus / f"{level_label}.png"
            plus_icon = Image.open(plus_path)
            bg = paste(bg, plus_icon, (plus_x, plus_y))
            drawtext = ImageDraw.Draw(bg)
        ttf = ImageFont.truetype(ttf_black_path, size=50)
        drawtext.text((level_x, level_y), level, font=ttf, fill=color, anchor="mm")

        scores = [d for d in records if d["level_index"] == i]
        if not scores:
            ttf = ImageFont.truetype(ttf_bold_path, size=20)
            drawtext.text(
                (dsra_x, dsra_y),
                f"{song_data['ds'][i]}->---",
                font=ttf,
                fill=color,
                anchor="mm",
            )
            continue

        score = scores[0]
        if score["ra"] <= 0:
            drawtext.text(
                (dsra_x, dsra_y),
                f"{song_data['ds'][i]}->---",
                font=ttf,
                fill=color,
                anchor="mm",
            )
            continue

        achieve = str(score["achievements"])
        if "." not in achieve:
            achieve = f"{achieve}.0"
        achieve1, achieve2 = achieve.split(".")
        achieve2 = (achieve2.ljust(4, "0"))[:4]
        achieve = f"{achieve1}.{achieve2}%"
        ds = song_data["ds"][i]
        fc = score["fc"]
        fs = score["fs"]
        ra = str(score["ra"])
        rate = score["rate"]

        # 达成率
        ttf = ImageFont.truetype(ttf_bold_path, size=43)
        drawtext.text(
            (achieve_x, achieve_y), achieve, font=ttf, fill=color, anchor="mm"
        )

        # 评价
        rate_path = f"./Static/Maimai/Rate/{rate}.png"
        rate = Image.open(rate_path)
        rate = resize_image(rate, 0.5)
        bg = paste(bg, rate, (rate_x, rate_y))
        drawtext = ImageDraw.Draw(bg)

        # fc & fs
        if fc:
            fc_path = maimai_Static / f"playicon_{fc}.png"
            fc = Image.open(fc_path)
            fc = resize_image(fc, 0.33)
            bg = paste(bg, fc, (fc_x, fc_y))
            drawtext = ImageDraw.Draw(bg)

        if fs:
            fs_path = maimai_Static / f"playicon_{fs}.png"
            fs = Image.open(fs_path)
            fs = resize_image(fs, 0.33)
            bg = paste(bg, fs, (fs_x, fs_y))
            drawtext = ImageDraw.Draw(bg)

        # 定数->ra
        ttf = ImageFont.truetype(ttf_bold_path, size=20)
        drawtext.text(
            (dsra_x, dsra_y), f"{ds}->{ra}", font=ttf, fill=color, anchor="mm"
        )

    ttf = ImageFont.truetype(ttf2_regular_path, size=16)
    bg = text(
        text(
            bg,
            xy=(bg.width - 16, bg.height - 32),
            font=ttf,
            text="感谢水鱼查分器提供数据支持",
            fill=(255, 255, 255, 205),
            anchor="rb",
        ),
        xy=(bg.width - 16, bg.height - 16),
        font=ttf,
        text=f"Ver.{config.version[0]}.{config.version[1]}-{config.version[2]}",
        fill=(255, 255, 255, 205),
        anchor="rb",
    )

    img_byte_arr = BytesIO()
    bg = bg.convert("RGB")
    bg.save(img_byte_arr, format="JPEG")
    img_byte_arr.seek(0)
    img_bytes = img_byte_arr.getvalue()

    return img_bytes


async def utage_music_info(song_data, index=0):
    # 底图
    bg = Image.open("./Static/Maimai/Chart/background_utage.png")

    # 歌曲封面
    cover_path = f"./Cache/Jacket/{int(song_data['id']) % 10000}.png"
    if not os.path.exists(cover_path):
        async with AsyncClient(http2=True) as session:
            resp = await session.get(
                f"https://assets2.lxns.net/maimai/jacket/{int(song_data['id']) % 10000}.png"
            )
            async with aiofiles.open(cover_path, "wb") as fd:
                await fd.write(await resp.aread())
    cover = Image.open(cover_path).resize((295, 295))
    bg = paste(bg, cover, (204, 440))
    drawtext = ImageDraw.Draw(bg)

    # 绘制标题
    song_title = song_data["title"]
    if len(song_data["charts"]) > 1:
        song_title += f" [{index}]"
    ttf = ImageFont.truetype(ttf_bold_path, size=40)
    title_position = (545, 626)
    max_width = 565
    ellipsis = "…"
    # 检查文本的宽度是否超过最大宽度
    if ttf.getlength(song_title) <= max_width:
        # 文本未超过最大宽度,直接绘制
        drawtext.text(title_position, song_title, font=ttf, fill=(0, 0, 0))
    else:
        # 文本超过最大宽度,截断并添加省略符号
        truncated_title = song_title
        while (
            ttf.getlength(f"{truncated_title}{ellipsis}") > max_width
            and len(truncated_title) > 0
        ):
            truncated_title = truncated_title[:-1].strip()
        drawtext.text(
            title_position, truncated_title + ellipsis, font=ttf, fill=(0, 0, 0)
        )

    # 绘制曲师
    song_artist = song_data["basic_info"]["artist"]
    ttf = ImageFont.truetype(ttf_regular_path, size=30)
    artist_position = (545, 694)
    max_width = 565
    ellipsis = "…"
    # 检查文本的宽度是否超过最大宽度
    if ttf.getlength(song_artist) <= max_width:
        # 文本未超过最大宽度,直接绘制
        drawtext.text(artist_position, song_artist, font=ttf, fill=(0, 0, 0))
    else:
        # 文本超过最大宽度,截断并添加省略符号
        truncated_title = song_artist
        while (
            ttf.getlength(f"{truncated_title}{ellipsis}") > max_width
            and len(truncated_title) > 0
        ):
            truncated_title = truncated_title[:-1].strip()
        drawtext.text(
            artist_position, truncated_title + ellipsis, font=ttf, fill=(0, 0, 0)
        )

    # id
    ttf = ImageFont.truetype(ttf_bold_path, size=28)
    id_position = (239, 872)
    drawtext.text(
        id_position,
        song_data["id"],
        anchor="mm",
        font=ttf,
        fill=(53, 74, 164),
    )
    # bpm
    song_bpm = str(song_data["basic_info"]["bpm"])
    bpm_position = (341, 872)
    drawtext.text(
        bpm_position,
        song_bpm,
        anchor="mm",
        font=ttf,
        fill=(53, 74, 164),
    )
    # 分类
    ttf = ImageFont.truetype(ttf2_bold_path, size=28)
    song_genre = song_data["basic_info"]["genre"]
    genre_position = (544, 872)
    drawtext.text(
        genre_position,
        song_genre,
        anchor="mm",
        font=ttf,
        fill=(53, 74, 164),
    )
    # 谱面类型
    ttf = ImageFont.truetype(ttf_bold_path, size=28)
    song_type = song_data["type"]
    type_path = maimai_MusicType / f"{song_type}.png"
    type = Image.open(type_path)
    type = resize_image(type, 0.7)
    bg = paste(bg, type, (694, 852))
    # version
    song_ver = song_data["basic_info"]["from"]
    song_ver = Image.open(maimai_Version / f"{song_ver}.png")
    song_ver = resize_image(song_ver, 0.8)
    bg = paste(bg, song_ver, (860, 768))
    drawtext = ImageDraw.Draw(bg)

    # 等级
    ttf = ImageFont.truetype(ttf_black_path, size=50)
    song_level = song_data["level"][0].replace("?", str())
    drawtext.text((650, 1046), song_level, anchor="mm", font=ttf, fill=(131, 19, 158))

    # 物量
    ttf = ImageFont.truetype(ttf_bold_path, size=40)
    chart = song_data["charts"][index]
    notes_x = 310
    notes_y = 1258
    notes = chart["notes"]
    if song_type == "SD":
        notes.insert(3, 0)
    for note in notes:
        if note > 0:
            notes_position = (notes_x, notes_y)
            drawtext.text(
                notes_position,
                str(note),
                anchor="mm",
                font=ttf,
                fill=(131, 19, 158),
            )
        notes_x += 170
    total_num = np.sum(notes)
    drawtext.text(
        (438, 1415),
        str(total_num),
        anchor="mm",
        font=ttf,
        fill=(131, 19, 158),
    )
    dx_num = total_num * 3
    drawtext.text(
        (863, 1415),
        str(dx_num),
        anchor="mm",
        font=ttf,
        fill=(131, 19, 158),
    )

    # 谱师
    ttf = ImageFont.truetype(ttf_regular_path, size=20)
    drawtext.text(
        (730, 1545), chart["charter"], anchor="mm", font=ttf, fill=(131, 19, 158)
    )

    ttf = ImageFont.truetype(ttf2_regular_path, size=16)
    bg = text(
        text(
            bg,
            xy=(bg.width - 16, bg.height - 32),
            font=ttf,
            text="感谢水鱼查分器提供数据支持",
            fill=(255, 255, 255, 205),
            anchor="rb",
        ),
        xy=(bg.width - 16, bg.height - 16),
        font=ttf,
        text=f"Ver.{config.version[0]}.{config.version[1]}-{config.version[2]}",
        fill=(255, 255, 255, 205),
        anchor="rb",
    )

    img_byte_arr = BytesIO()
    bg = bg.convert("RGB")
    bg.save(img_byte_arr, format="JPEG")
    img_byte_arr.seek(0)
    img_bytes = img_byte_arr.getvalue()

    return img_bytes


async def score_info(song_data, index):
    # 底图
    bg = Image.open("./Static/Maimai/Achievements/background.png")

    # 歌曲封面
    cover_path = f"./Cache/Jacket/{int(song_data['id']) % 10000}.png"
    if not os.path.exists(cover_path):
        async with AsyncClient(http2=True) as session:
            resp = await session.get(
                f"https://assets2.lxns.net/maimai/jacket/{int(song_data['id']) % 10000}.png"
            )
            async with aiofiles.open(cover_path, "wb") as fd:
                await fd.write(await resp.aread())
    cover = Image.open(cover_path).resize((295, 295))
    bg = paste(bg, cover, (204, 440))
    drawtext = ImageDraw.Draw(bg)

    # 绘制标题
    song_title = song_data["title"]
    ttf = ImageFont.truetype(ttf_bold_path, size=40)
    title_position = (545, 626)
    max_width = 565
    ellipsis = "…"
    # 检查文本的宽度是否超过最大宽度
    if ttf.getlength(song_title) <= max_width:
        # 文本未超过最大宽度,直接绘制
        drawtext.text(title_position, song_title, font=ttf, fill=(0, 0, 0))
    else:
        # 文本超过最大宽度,截断并添加省略符号
        truncated_title = song_title
        while (
            ttf.getlength(f"{truncated_title}{ellipsis}") > max_width
            and len(truncated_title) > 0
        ):
            truncated_title = truncated_title[:-1].strip()
        drawtext.text(
            title_position, truncated_title + ellipsis, font=ttf, fill=(0, 0, 0)
        )

    # 绘制曲师
    song_artist = f"曲：{song_data['basic_info']['artist']}"
    ttf = ImageFont.truetype(ttf2_regular_path, size=30)
    artist_position = (545, 694)
    max_width = 565
    ellipsis = "…"
    # 检查文本的宽度是否超过最大宽度
    if ttf.getlength(song_artist) <= max_width:
        # 文本未超过最大宽度,直接绘制
        drawtext.text(artist_position, song_artist, font=ttf, fill=(0, 0, 0))
    else:
        # 文本超过最大宽度,截断并添加省略符号
        truncated_title = song_artist
        while (
            ttf.getlength(f"{truncated_title}{ellipsis}") > max_width
            and len(truncated_title) > 0
        ):
            truncated_title = truncated_title[:-1].strip()
        drawtext.text(
            artist_position, truncated_title + ellipsis, font=ttf, fill=(0, 0, 0)
        )

    # id
    ttf = ImageFont.truetype(ttf_bold_path, size=28)
    id_position = (239, 872)
    drawtext.text(
        id_position,
        song_data["id"],
        anchor="mm",
        font=ttf,
        fill=(53, 74, 164),
    )
    # bpm
    song_bpm = str(song_data["basic_info"]["bpm"])
    bpm_position = (341, 872)
    drawtext.text(
        bpm_position,
        song_bpm,
        anchor="mm",
        font=ttf,
        fill=(53, 74, 164),
    )
    # 分类
    ttf = ImageFont.truetype(ttf2_bold_path, size=28)
    song_genre = song_data["basic_info"]["genre"]
    genre_position = (544, 872)
    drawtext.text(
        genre_position,
        song_genre,
        anchor="mm",
        font=ttf,
        fill=(53, 74, 164),
    )
    # 谱面类型
    ttf = ImageFont.truetype(ttf_bold_path, size=28)
    song_type = song_data["type"]
    type_path = maimai_MusicType / f"{song_type}.png"
    type = Image.open(type_path)
    type = resize_image(type, 0.7)
    bg = paste(bg, type, (694, 852))
    # version
    song_ver = song_data["basic_info"]["from"]
    song_ver = Image.open(maimai_Version / f"{song_ver}.png")
    song_ver = resize_image(song_ver, 0.8)
    bg = paste(bg, song_ver, (860, 768))
    drawtext = ImageDraw.Draw(bg)

    # 等级
    ttf = ImageFont.truetype(ttf_black_path, size=36)
    song_level = song_data["level"][index]
    level_color = [
        (14, 117, 54),
        (214, 148, 19),
        (192, 33, 56),
        (103, 20, 141),
        (186, 126, 232),
    ]
    if "+" in song_level:
        song_level = song_level.replace("+", str())
        level_label = ["Basic", "Advanced", "Expert", "Master", "ReMASTER"][index]
        plus_path = maimai_Plus / f"{level_label}.png"
        plus_icon = Image.open(plus_path)
        bg = paste(bg, plus_icon, (302, 953))
        drawtext = ImageDraw.Draw(bg)
    drawtext.text(
        (251, 1000), song_level, anchor="mm", font=ttf, fill=level_color[index]
    )

    # 分数
    score_color = [(231, 144, 21), (227, 60, 117), (38, 143, 17), (130, 144, 203)]
    ttf = ImageFont.truetype(ttf_bold_path, size=36)
    chart = song_data["charts"][index]
    notes = chart["notes"]
    if song_type == "SD":
        notes.insert(3, 0)
    type_weight = [1, 2, 3, 1, 5]
    sum_score = 0
    for i in range(0, 5):
        sum_score += notes[i] * type_weight[i] * 500
    score_y = 1107
    for i in range(0, 7):
        score_x = 451
        type_index = i if i < 5 else 4
        great_weight = 0.2
        good_weight = 0.5
        if i > 3:
            ex_weight = [0, 0.25, 0.5][i - 4]
            great_weight = [0.2, 0.4, 0.5][i - 4]
            good_weight = 0.6
        for j in range(0, 4):
            if j > 1 and i in [4, 6]:
                break
            score_position = (score_x, score_y)
            if notes[type_index] > 0:
                weight = [0, great_weight, good_weight, 1][j]
                score = 1 - (
                    (sum_score - (500 * weight * type_weight[type_index])) / sum_score
                )
                if i > 3:
                    ex_weight = [ex_weight, 0.6, 0.7, 1][j]
                    ex_score = 1 - (
                        ((notes[-1] * 100) - (100 * ex_weight)) / (notes[-1] * 100)
                    )
                    score += ex_score / 100
                if score > 0:
                    score_text = f"{-(math.trunc(score * 1000000) / 1000000):.4%}"
                    drawtext.text(
                        score_position,
                        score_text,
                        anchor="mm",
                        font=ttf,
                        fill=score_color[j],
                    )
            score_x += 200
        score_y += 80

    # 物量
    ttf = ImageFont.truetype(ttf_bold_path, size=40)
    notes_x = 251
    notes_y = 1778
    for note in notes:
        if note > 0:
            notes_position = (notes_x, notes_y)
            drawtext.text(
                notes_position,
                str(note),
                anchor="mm",
                font=ttf,
                fill=(53, 74, 164),
            )
        notes_x += 200

    # 谱师
    song_charters = f"谱：{chart['charter']}"
    ttf = ImageFont.truetype(ttf2_regular_path, size=30)
    artist_position = (545, 729)
    max_width = 565
    ellipsis = "…"
    # 检查文本的宽度是否超过最大宽度
    if ttf.getlength(song_charters) <= max_width:
        # 文本未超过最大宽度,直接绘制
        drawtext.text(artist_position, song_charters, font=ttf, fill=(0, 0, 0))
    else:
        # 文本超过最大宽度,截断并添加省略符号
        truncated_title = song_charters
        while (
            ttf.getlength(f"{truncated_title}{ellipsis}") > max_width
            and len(truncated_title) > 0
        ):
            truncated_title = truncated_title[:-1].strip()
        drawtext.text(
            artist_position, truncated_title + ellipsis, font=ttf, fill=(0, 0, 0)
        )

    ttf = ImageFont.truetype(ttf2_regular_path, size=16)
    bg = text(
        text(
            bg,
            xy=(bg.width - 16, bg.height - 32),
            font=ttf,
            text="感谢水鱼查分器提供数据支持",
            fill=(255, 255, 255, 205),
            anchor="rb",
        ),
        xy=(bg.width - 16, bg.height - 16),
        font=ttf,
        text=f"Ver.{config.version[0]}.{config.version[1]}-{config.version[2]}",
        fill=(255, 255, 255, 205),
        anchor="rb",
    )

    img_byte_arr = BytesIO()
    bg = bg.convert("RGB")
    bg.save(img_byte_arr, format="JPEG")
    img_byte_arr.seek(0)
    img_bytes = img_byte_arr.getvalue()

    return img_bytes
