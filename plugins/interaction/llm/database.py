import shelve

from dill import Pickler, Unpickler

shelve.Pickler = Pickler
shelve.Unpickler = Unpickler

CONTEXT_LIMIT = 50 - 1


class ContextIdList(object):
    def __init__(self):
        self.data_path = "./data/llm.db"
        with shelve.open(self.data_path) as data:
            if "context_ids" not in data:
                data.setdefault("context_ids", dict())

    def get(self, id: str):
        with shelve.open(self.data_path) as data:
            if id not in data["context_ids"]:
                return None

            return data["context_ids"][id]

    def set(self, id: str, context_id: str):
        with shelve.open(self.data_path) as data:
            context_ids = data["context_ids"]

            context_ids[id] = context_id

            data["context_ids"] = context_ids


contextIdList = ContextIdList()
