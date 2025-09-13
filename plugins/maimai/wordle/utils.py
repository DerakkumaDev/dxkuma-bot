import sys
import unicodedata

from nonebot.exception import IgnoredException
from pykakasi import kakasi

from util.exceptions import ProcessedException
from .database import openchars
from .ranking import ranking
from .times import times

kks = kakasi()


async def generate_message_state(
    group_id: str, user_id: str, time: int
) -> tuple[bool, str, list]:
    game_data = await openchars.get_game_data(group_id)
    if not game_data:
        raise IgnoredException(ProcessedException)

    game_state = list()
    char_all_open = list()
    for game_content in game_data["game_contents"]:
        if game_content["is_correct"]:
            game_state.append(f"✓ {game_content['index']}. {game_content['title']}")
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
            await openchars.mark_content_as_correct(group_id, game_content["index"])

            await ranking.add_score(
                user_id,
                game_content["opc_times"],
                len(game_content["tips"]),
                game_content["pic_times"],
                game_content["aud_times"],
                True,
            )
            await times.add(user_id, time)

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
                await times.add(player, time)

            char_all_open.append(
                (
                    game_content["index"],
                    game_content["title"],
                    game_content["music_id"],
                )
            )
            game_state.append(f"✓ {game_content['index']}. {game_content['title']}")
        else:
            game_state.append(f"? {game_content['index']}. {display_title}")

    is_game_over = all(
        [game_content["is_correct"] for game_content in game_data["game_contents"]]
    )
    return is_game_over, "\r\n".join(game_state), char_all_open


async def check_music_id(
    group_id: str, music_ids: list[str], user_id: str, time: int
) -> list:
    game_data = await openchars.get_game_data(group_id)
    if not game_data:
        return []

    guess_success = list()
    for game_content in game_data["game_contents"]:
        if not game_content["is_correct"] and game_content["music_id"] in music_ids:
            await openchars.mark_content_as_correct(group_id, game_content["index"])

            await ranking.add_score(
                user_id,
                game_content["opc_times"],
                len(game_content["tips"]),
                game_content["pic_times"],
                game_content["aud_times"],
                True,
            )
            await times.add(user_id, time)

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
                await times.add(player, time)

            guess_success.append(
                (
                    game_content["index"],
                    game_content["title"],
                    game_content["music_id"],
                )
            )

    return guess_success


async def generate_success_state(group_id: str) -> str:
    game_data = await openchars.get_game_data(group_id)
    if not game_data:
        raise IgnoredException(ProcessedException)

    game_state = list()
    for game_content in game_data["game_contents"]:
        game_state.append(
            f"{'✓' if game_content['is_correct'] else '✕'} {game_content['index']}. {
                game_content['title']
            }"
        )
    return "\r\n".join(game_state)


def get_version_name(s: int, song_list: dict) -> str:
    versions = song_list["versions"]
    versions.append({"version": sys.maxsize})
    for i in range(len(versions) - 1):
        v = versions[i]
        if v["version"] <= s < versions[i + 1]["version"]:
            return v["title"]

    return str(s)
