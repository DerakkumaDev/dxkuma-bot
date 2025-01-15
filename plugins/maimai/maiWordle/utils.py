import unicodedata
from random import SystemRandom

from pykakasi import kakasi

from util.Data import get_music_data
from .ranking import ranking

random = SystemRandom()
kks = kakasi()


def check_game_over(game_data):
    return all(
        [game_content["is_correct"] for game_content in game_data["game_contents"]]
    )


async def generate_game_data():
    game_data = {"open_chars": list()}
    game_contents = list()
    temp_game_contents_ids = list()
    while len(game_contents) <= 4:
        music = random.choice(await get_music_data())
        if music["id"] in temp_game_contents_ids:
            continue
        game_contents.append(
            {
                "index": len(game_contents) + 1,
                "title": music["title"],
                "music_id": int(music["id"]),
                "is_correct": False,
                "tips": list(),
                "pic_times": 0,
                "aud_times": 0,
                "part": list(),
            }
        )
    game_data["game_contents"] = game_contents
    return game_data


async def generate_message_state(game_data, user_id):
    game_state = list()
    char_all_open = list()
    for game_content in game_data["game_contents"]:
        if game_content["is_correct"]:
            game_state.append(
                f"{game_content['index']}. {game_content["title"]}（已猜出）"
            )
            continue
        display_title = ""
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
                    display_title += "○"
                else:
                    display_title += "☆"
                is_all_open = False
        if is_all_open:
            game_content["is_correct"] = True

            await ranking.add_score(
                user_id,
                len(game_content["part"]),
                len(game_content["tips"]),
                game_content["pic_times"],
                game_content["aud_times"],
                True,
            )
            for player in game_content["part"]:
                if player == user_id:
                    continue
                await ranking.add_score(
                    player,
                    len(game_content["part"]),
                    len(game_content["tips"]),
                    game_content["pic_times"],
                    game_content["aud_times"],
                    False,
                )

            char_all_open.append(
                (
                    f"猜对了！第{game_content['index']}行的歌曲是{game_content['title']}",
                    game_content["music_id"],
                )
            )
            game_state.append(
                f"{game_content['index']}. {game_content["title"]}（已猜出）"
            )
        else:
            game_state.append(f"{game_content['index']}. {display_title}")

    is_game_over = check_game_over(game_data)
    # if is_game_over:
    #     game_state.append("所有歌曲已全部被开出来啦,游戏结束。")
    return is_game_over, "\r\n".join(game_state), char_all_open, game_data


async def check_music_id(game_data, music_ids: list, user_id):
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
                    len(game_content["part"]),
                    len(game_content["tips"]),
                    game_content["pic_times"],
                    game_content["aud_times"],
                    True,
                )
                for player in game_content["part"]:
                    if player == user_id:
                        continue
                    await ranking.add_score(
                        player,
                        len(game_content["part"]),
                        len(game_content["tips"]),
                        game_content["pic_times"],
                        game_content["aud_times"],
                        False,
                    )

                guess_success.append(
                    (
                        f"猜对了！第{game_content['index']}行的歌曲是{game_content['title']}",
                        game_content["music_id"],
                    )
                )
    return guess_success, game_data


def generate_success_state(game_data):
    game_state = list()
    for game_content in game_data["game_contents"]:
        game_state.append(f"{game_content['index']}. {game_content["title"]}")
    return "\r\n".join(game_state)


def check_char_in_text(text: str, char: str):
    text = text.casefold()
    if char.casefold() in text:
        return True

    for c in kks.convert(char):
        for v in c.values():
            if v.casefold() in text:
                return True

    return False
