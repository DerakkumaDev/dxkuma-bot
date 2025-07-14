import shelve

from dill import Pickler, Unpickler

from .utils import generate_game_data, check_char_in_text

shelve.Pickler = Pickler
shelve.Unpickler = Unpickler


class OpenChars(object):
    def __init__(self):
        self.data_path = "./data/wordle.db"

    async def start(self, group_id: str):
        with shelve.open(self.data_path) as data:
            if group_id in data:
                game_data = data[group_id]
                return game_data

            game_data = data.setdefault(group_id, await generate_game_data())
            return game_data

    def game_over(self, group_id: str):
        with shelve.open(self.data_path) as data:
            if group_id not in data:
                return

            del data[group_id]

    def open_char(self, group_id: str, chars: str, user_id: str):
        with shelve.open(self.data_path) as data:
            if group_id in data:
                game_data = data[group_id]
                if chars.casefold() in game_data["open_chars"]:
                    return False, None

                game_data["open_chars"].append(chars.casefold())
                for i in game_data["game_contents"]:
                    if check_char_in_text(i["title"], chars):
                        if user_id not in i["part"]:
                            i["part"].append(user_id)
                        i["opc_times"] += 1

                data[group_id] = game_data
                return True, game_data

        return None, None

    def get_game_data(self, group_id: str):
        with shelve.open(self.data_path) as data:
            if group_id in data:
                game_data = data[group_id]
                return game_data

        return

    async def update_game_data(self, group_id: str, game_data):
        with shelve.open(self.data_path) as data:
            if group_id in data:
                data[group_id] = game_data

            data.setdefault(group_id, await generate_game_data())


openchars = OpenChars()
