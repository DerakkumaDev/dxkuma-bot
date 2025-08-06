import sys
import unicodedata
from datetime import datetime

from numpy import random
from pykakasi import kakasi

from util.Data import get_music_data_lxns
from .ranking import ranking
from .times import times

kks = kakasi()


def check_game_over(game_data: dict) -> bool:
    return all(
        [game_content["is_correct"] for game_content in game_data["game_contents"]]
    )


async def generate_game_data() -> dict:
    rng = random.default_rng()
    game_data = {"open_chars": list()}
    game_contents = list()
    while len(game_contents) <= 4:
        music = rng.choice((await get_music_data_lxns())["songs"])
        game_contents.append(
            {
                "index": len(game_contents) + 1,
                "title": music["title"],
                "music_id": music["id"],
                "is_correct": False,
                "tips": list(),
                "pic_times": 0,
                "aud_times": 0,
                "opc_times": 0,
                "part": list(),
            }
        )
    game_data["game_contents"] = game_contents
    return game_data


async def generate_message_state(
    game_data: dict, user_id: str, time: int
) -> tuple[bool, str, list]:
    now = datetime.fromtimestamp(time)
    game_state = list()
    char_all_open = list()
    for game_content in game_data["game_contents"]:
        if game_content["is_correct"]:
            game_state.append(
                f"{game_content['index']}. {game_content['title']}（已猜出）"
            )
            continue
        display_title = str()
        is_all_open = True
        for c in game_content["title"]:
            if (
                c.casefold() in game_data["open_chars"]
                or c == " "
                or not c.isprintable()
                or [
                    None
                    for d in kks.convert(c)
                    if [None for b in d.values() if b in game_data["open_chars"]]
                ]
            ):
                display_title += c
            else:
                unicode_name = unicodedata.name(c)
                if (
                    "LATIN" in unicode_name and "LETTER" in unicode_name
                ) or "DIGIT" in unicode_name:
                    display_title += "□"
                elif (
                    "CJK" in unicode_name
                    or "HIRAGANA LETTER" in unicode_name
                    or "KATAKANA LETTER" in unicode_name
                ):
                    display_title += "◎"
                else:
                    display_title += "◇"
                is_all_open = False
        if is_all_open:
            game_content["is_correct"] = True

            await ranking.add_score(
                user_id,
                game_content["opc_times"],
                len(game_content["tips"]),
                game_content["pic_times"],
                game_content["aud_times"],
                True,
            )
            await times.add(user_id, now.year, now.month, now.day)
            for player in game_content["part"]:
                if player == user_id:
                    continue
                await ranking.add_score(
                    player,
                    game_content["opc_times"],
                    len(game_content["tips"]),
                    game_content["pic_times"],
                    game_content["aud_times"],
                    False,
                )
                await times.add(player, now.year, now.month, now.day)

            char_all_open.append(
                (
                    game_content["index"],
                    game_content["title"],
                    game_content["music_id"],
                )
            )
            game_state.append(
                f"{game_content['index']}. {game_content['title']}（已猜出）"
            )
        else:
            game_state.append(f"{game_content['index']}. {display_title}")

    is_game_over = check_game_over(game_data)
    # if is_game_over:
    #     game_state.append("所有歌曲已全部被开出来啦,游戏结束。")
    return is_game_over, "\r\n".join(game_state), char_all_open


async def check_music_id(
    game_data: dict, music_ids: list[str], user_id: str, time: int
) -> list:
    now = datetime.fromtimestamp(time)
    guess_success = list()
    for music_id in music_ids:
        for game_content in game_data["game_contents"]:
            if (
                int(music_id) == game_content["music_id"]
                and not game_content["is_correct"]
            ):
                game_content["is_correct"] = True

                await ranking.add_score(
                    user_id,
                    game_content["opc_times"],
                    len(game_content["tips"]),
                    game_content["pic_times"],
                    game_content["aud_times"],
                    True,
                )
                await times.add(user_id, now.year, now.month, now.day)
                for player in game_content["part"]:
                    if player == user_id:
                        continue
                    await ranking.add_score(
                        player,
                        game_content["opc_times"],
                        len(game_content["tips"]),
                        game_content["pic_times"],
                        game_content["aud_times"],
                        False,
                    )
                    await times.add(player, now.year, now.month, now.day)

                guess_success.append(
                    (
                        game_content["index"],
                        game_content["title"],
                        game_content["music_id"],
                    )
                )
    return guess_success


def generate_success_state(game_data: dict) -> str:
    game_state = list()
    for game_content in game_data["game_contents"]:
        game_state.append(f"{game_content['index']}. {game_content['title']}")
    return "\r\n".join(game_state)


def check_char_in_text(text: str, char: str) -> bool:
    text = text.casefold()
    if char.casefold() in text:
        return True

    for c in kks.convert(char):
        for v in c.values():
            if v.casefold() in text:
                return True

    return False


def get_version_name(s: int, song_list: dict) -> str:
    versions = song_list["versions"]
    versions.append({"version": sys.maxsize})
    for i in range(len(versions) - 1):
        v = versions[i]
        if v["version"] <= s < versions[i + 1]["version"]:
            return v["title"]
