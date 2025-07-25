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

            if "chat_mode" not in data:
                data.setdefault("chat_mode", dict())

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

    def get_chatmode(self, id: str):
        with shelve.open(self.data_path) as data:
            if id not in data["chat_mode"]:
                return True

            return data["chat_mode"][id]

    def set_chatmode(self, id: str, chat_mode: bool):
        with shelve.open(self.data_path) as data:
            chat_modes = data["chat_mode"]

            chat_modes[id] = chat_mode

            data["chat_mode"] = chat_modes


contextIdList = ContextIdList()
