import shelve
import time

import nanoid
from dill import Pickler, Unpickler
from rapidfuzz import fuzz_py as fuzz
from rapidfuzz import process_py as process

shelve.Pickler = Pickler
shelve.Unpickler = Unpickler


class ArcadeManager(object):
    def __init__(self):
        self.data_path = "./data/queue.db"
        with shelve.open(self.data_path) as data:
            if "arcades" not in data:
                data.setdefault("arcades", dict())
            if "names" not in data:
                data.setdefault("names", dict())
            if "aliases" not in data:
                data.setdefault("aliases", dict())
            if "bindings" not in data:
                data.setdefault("bindings", dict())

    def get_arcade(self, arcade_id: str):
        with shelve.open(self.data_path) as data:
            if arcade_id not in data["arcades"]:
                return None

            arcade = data["arcades"][arcade_id]
            if arcade["last_action"] is None:
                return arcade

            last_action_time = arcade["last_action"]["time"]
            now = time.localtime()
            today = time.mktime(
                (now.tm_year, now.tm_mon, now.tm_mday, 4, 0, 0, 0, 0, -1)
            )
            if last_action_time >= today or now.tm_hour < 4:
                return arcade

            arcade = self.reset(arcade_id, int(today))
            return arcade

    def get_arcade_id(self, arcade_name: str):
        with shelve.open(self.data_path) as data:
            if arcade_name not in data["names"]:
                return None

            return data["names"][arcade_name]

    def get_bounden_arcade_ids(self, group_id: int):
        with shelve.open(self.data_path) as data:
            if group_id not in data["bindings"]:
                return list()

            return data["bindings"][group_id]

    def create(self, arcade_name: str):
        with shelve.open(self.data_path) as data:
            arcades = data["arcades"]
            names = data["names"]

            if arcade_name in names:
                return None

            arcade_id = nanoid.generate()
            arcades[arcade_id] = {
                "name": arcade_name,
                "count": 0,
                "action_times": 0,
                "last_action": None,
                "aliases": list(),
                "bindings": list(),
            }
            names[arcade_name] = arcade_id

            data["arcades"] = arcades
            data["names"] = names
            return arcade_id

    def bind(self, group_id: int, arcade_id: str):
        with shelve.open(self.data_path) as data:
            arcades = data["arcades"]
            bindings = data["bindings"]

            if group_id in arcades[arcade_id]["bindings"]:
                return False

            if group_id not in bindings:
                bindings[group_id] = list()
            elif arcade_id in bindings[group_id]:
                return False

            arcades[arcade_id]["bindings"].append(group_id)
            bindings[group_id].append(arcade_id)

            data["arcades"] = arcades
            data["bindings"] = bindings
            return True

    def unbind(self, group_id: int, arcade_id: str):
        with shelve.open(self.data_path) as data:
            arcades = data["arcades"]
            bindings = data["bindings"]

            if group_id not in arcades[arcade_id]["bindings"]:
                return False

            if group_id not in bindings:
                return False

            if arcade_id not in bindings[group_id]:
                return False

            arcades[arcade_id]["bindings"].remove(group_id)
            bindings[group_id].remove(arcade_id)
            if len(arcades[arcade_id]["bindings"]) < 1:
                names = data["names"]
                del names[arcades[arcade_id]["name"]]
                data["names"] = names
                if len(arcades[arcade_id]["aliases"]) > 0:
                    aliases = data["aliases"]
                    for alias in arcades[arcade_id]["aliases"]:
                        aliases[alias].remove(arcade_id)

                    data["aliases"] = aliases

                del arcades[arcade_id]

            data["arcades"] = arcades
            data["bindings"] = bindings
            return True

    def search(self, group_id: int, word: str):
        bounden_arcade_ids = self.get_bounden_arcade_ids(group_id)
        names = list()
        for arcade_id in bounden_arcade_ids:
            arcade = self.get_arcade(arcade_id)
            if word in arcade["aliases"]:
                return [arcade_id]

            names.append(arcade["name"])

        results = process.extract(word, names, scorer=fuzz.QRatio, score_cutoff=100)
        filtered = [
            arcade_id
            for arcade_id in [self.get_arcade_id(name) for name, _, _ in results]
        ]
        matched_ids = list(dict.fromkeys(filtered))
        if len(matched_ids) > 0:
            return matched_ids

        results = process.extract(word, names, scorer=fuzz.WRatio, score_cutoff=80)
        filtered = [
            arcade_id
            for arcade_id in [self.get_arcade_id(name) for name, _, _ in results]
        ]
        matched_ids = list(dict.fromkeys(filtered))

        return matched_ids

    def search_all(self, word: str):
        names = list()
        with shelve.open(self.data_path) as data:
            for arcade_id, arcade in data["arcades"].items():
                if word in arcade["aliases"]:
                    return [arcade_id]

                names.append(arcade["name"])

        results = process.extract(word, names, scorer=fuzz.QRatio, score_cutoff=100)
        filtered = [
            arcade_id
            for arcade_id in [self.get_arcade_id(name) for name, _, _ in results]
        ]
        matched_ids = list(dict.fromkeys(filtered))
        if len(matched_ids) > 0:
            return matched_ids

        results = process.extract(word, names, scorer=fuzz.WRatio, score_cutoff=80)
        filtered = [
            arcade_id
            for arcade_id in [self.get_arcade_id(name) for name, _, _ in results]
        ]
        matched_ids = list(dict.fromkeys(filtered))

        return matched_ids

    def add_ailas(self, arcade_id: str, alias: str):
        with shelve.open(self.data_path) as data:
            arcades = data["arcades"]
            aliases = data["aliases"]

            if alias in arcades[arcade_id]["aliases"]:
                return False

            if alias not in aliases:
                aliases[alias] = list()
            elif arcade_id in aliases[alias]:
                return False

            arcades[arcade_id]["aliases"].append(alias)
            aliases[alias].append(arcade_id)

            data["arcades"] = arcades
            data["aliases"] = aliases
            return True

    def remove_ailas(self, arcade_id: str, alias: str):
        with shelve.open(self.data_path) as data:
            arcades = data["arcades"]
            aliases = data["aliases"]

            if alias not in arcades[arcade_id]["aliases"]:
                return False

            if alias not in aliases:
                return False

            if arcade_id not in aliases[alias]:
                return False

            arcades[arcade_id]["aliases"].remove(alias)
            aliases[alias].remove(arcade_id)

            data["arcades"] = arcades
            data["aliases"] = aliases
            return True

    def do_action(
        self,
        arcade_id: str,
        type: str,
        group_id: int,
        operator: int,
        time: int,
        num: int,
    ):
        with shelve.open(self.data_path) as data:
            arcades = data["arcades"]

            arcade = arcades[arcade_id]
            before = arcade["count"]
            match type:
                case "add":
                    new_count = arcade["count"] + num
                    if new_count > 50:
                        return arcade

                    arcade["count"] = new_count
                case "remove":
                    new_count = arcade["count"] - num
                    if new_count < 0:
                        return arcade

                    arcade["count"] = new_count
                case "set":
                    if num < 0 or num > 50 or arcade["count"] == num:
                        return arcade

                    arcade["count"] = num

            arcade["action_times"] += 1

            arcade["last_action"] = {
                "group": group_id,
                "operator": operator,
                "time": time,
                "action": {"type": type, "before": before, "num": num},
            }
            arcades[arcade_id] = arcade

            data["arcades"] = arcades
            return arcade

    def reset(self, arcade_id: str, time: int):
        with shelve.open(self.data_path) as data:
            arcades = data["arcades"]

            arcade = arcades[arcade_id]
            arcade["action_times"] = 0
            before = arcade["count"]
            if before > 0:
                arcade["last_action"] = {
                    "group": -1,
                    "operator": -1,
                    "time": time,
                    "action": {"type": "set", "before": before, "num": 0},
                }
            arcades[arcade_id] = arcade

            data["arcades"] = arcades
            return arcade


arcadeManager = ArcadeManager()
