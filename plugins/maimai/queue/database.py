import shelve
from datetime import datetime
from typing import Any, Optional

import nanoid
from dill import Pickler, Unpickler
from rapidfuzz import fuzz
from rapidfuzz import process

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

    def get_arcade(self, arcade_id: str) -> Optional[dict[str, Any]]:
        with shelve.open(self.data_path) as data:
            if arcade_id not in data["arcades"]:
                return

            arcade = data["arcades"][arcade_id]
            if arcade["last_action"] is None:
                return arcade

            last_action_time = datetime.fromtimestamp(arcade["last_action"]["time"])
            now = datetime.now()
            today = datetime(now.year, now.month, now.day, 4, 0, 0, 0)
            if last_action_time >= today or now.hour < 4:
                return arcade

            arcade = self.reset(arcade_id, int(today.timestamp()))
            return arcade

    def get_arcade_id(self, arcade_name: str) -> Optional[str]:
        with shelve.open(self.data_path) as data:
            if arcade_name not in data["names"]:
                return

            return data["names"][arcade_name]

    def get_bounden_arcade_ids(self, group_id: int) -> list[str]:
        with shelve.open(self.data_path) as data:
            if group_id not in data["bindings"]:
                return list()

            return data["bindings"][group_id]

    def create(self, arcade_name: str) -> Optional[str]:
        with shelve.open(self.data_path) as data:
            arcades = data["arcades"]
            names = data["names"]

            if arcade_name in names:
                return

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

    def bind(self, group_id: int, arcade_id: str) -> bool:
        with shelve.open(self.data_path) as data:
            arcades = data["arcades"]
            bindings = data["bindings"]

            if group_id in arcades[arcade_id]["bindings"]:
                return False

            bindings.setdefault(group_id, list())
            if arcade_id in bindings[group_id]:
                return False

            arcades[arcade_id]["bindings"].append(group_id)
            bindings[group_id].append(arcade_id)

            data["arcades"] = arcades
            data["bindings"] = bindings
            return True

    def unbind(self, group_id: int, arcade_id: str) -> bool:
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

    def search(self, group_id: int, word: str) -> list[str]:
        bounden_arcade_ids = self.get_bounden_arcade_ids(group_id)
        matched_ids = list()
        for arcade_id in bounden_arcade_ids:
            arcade = self.get_arcade(arcade_id)
            if arcade is None:
                continue

            if word in arcade["aliases"]:
                matched_ids.append(arcade_id)

            if word == arcade["name"]:
                matched_ids.append(arcade_id)

        return matched_ids

    def _filter_arcade_ids(
        self, word: str, names: list[str], scorer, score_cutoff: int
    ) -> list[str]:
        results = process.extract(word, names, scorer=scorer, score_cutoff=score_cutoff)
        filtered = [
            arcade_id
            for arcade_id in [self.get_arcade_id(name) for name, _, _ in results]
            if arcade_id is not None
        ]
        return list(dict.fromkeys(filtered))

    def search_all(self, word: str) -> list[str]:
        names = list()
        with shelve.open(self.data_path) as data:
            for arcade_id, arcade in data["arcades"].items():
                if word in arcade["aliases"]:
                    return [arcade_id]

                names.append(arcade["name"])

        matched_ids = self._filter_arcade_ids(
            word, names, scorer=fuzz.QRatio, score_cutoff=100
        )
        if len(matched_ids) > 0:
            return matched_ids

        matched_ids = self._filter_arcade_ids(
            word, names, scorer=fuzz.WRatio, score_cutoff=80
        )

        return matched_ids

    @property
    def all_arcade_ids(self) -> list[str]:
        with shelve.open(self.data_path) as data:
            return data["arcades"].keys()

    def add_alias(self, arcade_id: str, alias: str) -> bool:
        with shelve.open(self.data_path) as data:
            arcades = data["arcades"]
            aliases = data["aliases"]

            if alias in arcades[arcade_id]["aliases"]:
                return False

            aliases.setdefault(alias, list())
            if arcade_id in aliases[alias]:
                return False

            arcades[arcade_id]["aliases"].append(alias)
            aliases[alias].append(arcade_id)

            data["arcades"] = arcades
            data["aliases"] = aliases
            return True

    def remove_alias(self, arcade_id: str, alias: str) -> bool:
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
    ) -> dict[str, Any]:
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
                "before": before,
            }
            arcades[arcade_id] = arcade

            data["arcades"] = arcades
            return arcade

    def reset(self, arcade_id: str, time: int) -> dict[str, Any]:
        with shelve.open(self.data_path) as data:
            arcades = data["arcades"]

            arcade = arcades[arcade_id]
            arcade["action_times"] = 0
            if arcade["count"] > 0:
                arcade["last_action"] = {
                    "group": -1,
                    "operator": -1,
                    "time": time,
                    "before": arcade["count"],
                }
                arcade["count"] = 0

            arcades[arcade_id] = arcade

            data["arcades"] = arcades
            return arcade


arcadeManager = ArcadeManager()
