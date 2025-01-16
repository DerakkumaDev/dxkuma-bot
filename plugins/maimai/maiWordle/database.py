import shelve

from dill import Pickler, Unpickler

from .utils import generate_game_data, check_char_in_text

shelve.Pickler = Pickler
shelve.Unpickler = Unpickler


class OpenChars(object):
    def __init__(self):
        self.data_path = "./data/wordle.db"

    async def start(self, group_id: int):
        with shelve.open(self.data_path) as data:
            if str(group_id) in data:
                game_data = data[str(group_id)]
                return game_data

            game_data = data.setdefault(str(group_id), await generate_game_data())
            return game_data

    async def game_over(self, group_id: int):
        with shelve.open(self.data_path) as data:
            if str(group_id) not in data:
                return

            data.pop(str(group_id))

    async def open_char(self, group_id: int, chars: str, user_id: int):
        with shelve.open(self.data_path) as data:
            if str(group_id) in data:
                game_data = data[str(group_id)]
                if chars.casefold() in game_data["open_chars"]:
                    return False, None

                game_data["open_chars"].append(chars.casefold())
                for i in game_data["game_contents"]:
                    if check_char_in_text(i["title"], chars):
                        i["opc_times"] += 1
                        i["part"].add(user_id)

                data[str(group_id)] = game_data
                return True, game_data

        return None, None

    async def get_game_data(self, group_id: int):
        with shelve.open(self.data_path) as data:
            if str(group_id) in data:
                game_data = data[str(group_id)]
                return game_data

        return None

    async def update_game_data(self, group_id: int, game_data):
        with shelve.open(self.data_path) as data:
            if str(group_id) in data:
                data[str(group_id)] = game_data

            data.setdefault(str(group_id), await generate_game_data())


openchars = OpenChars()
