import shelve

from dill import Pickler, Unpickler

shelve.Pickler = Pickler
shelve.Unpickler = Unpickler

CONTEXT_LIMIT = 50 - 1


class ContextManager(object):
    def __init__(self):
        self.data_path = "./data/llm.db"
        with shelve.open(self.data_path) as data:
            if "contexts" not in data:
                data.setdefault("contexts", dict())

            if "chat_mode" not in data:
                data.setdefault("chat_mode", dict())

    def get_context(self, id: str):
        with shelve.open(self.data_path) as data:
            if id not in data["contexts"]:
                return list()

            return data["contexts"][id]

    def add_to_context(self, id: str, role: str, message: str):
        with shelve.open(self.data_path) as data:
            contexts = data["contexts"]

            if id not in contexts:
                contexts.setdefault(id, list())

            while len(contexts[id]) >= CONTEXT_LIMIT:
                contexts[id].pop(0)

            contexts[id].append({"role": role, "content": message})

            data["contexts"] = contexts

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


contextManager = ContextManager()
