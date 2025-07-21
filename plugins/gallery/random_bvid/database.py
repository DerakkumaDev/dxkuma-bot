import shelve

from dill import Pickler, Unpickler
from numpy import random

shelve.Pickler = Pickler
shelve.Unpickler = Unpickler


class bvidList(object):
    def __init__(self):
        self.data_path = "./data/bvid.db"
        with shelve.open(self.data_path) as data:
            if "bvid" not in data:
                data.setdefault("bvid", list())

    @property
    def random_bvid(self) -> str:
        rng = random.default_rng()
        with shelve.open(self.data_path) as data:
            bvids = data["bvid"]
            return rng.choice(bvids)

    def add(self, bvid: str) -> bool:
        with shelve.open(self.data_path) as data:
            bvids = data["bvid"]
            if bvid in bvids:
                return False

            bvids.append(bvid)
            data["bvid"] = bvids

        return True

    def remove(self, bvid: str) -> None:
        with shelve.open(self.data_path) as data:
            bvids = data["bvid"]
            bvids.remove(bvid)
            data["bvid"] = bvids

    @property
    def count(self) -> int:
        with shelve.open(self.data_path) as data:
            bvids = data["bvid"]
            return len(bvids)


bvidList = bvidList()
