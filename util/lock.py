from enum import Enum, unique

from anyio import Semaphore

from .config import config


@unique
class States(Enum):
    PROCESSING = 0
    PROCESSED = 1
    SKIPED = 2
    NEED_TO_SWITCH = 3


class Lock(object):
    def __init__(self):
        self.state = States.PROCESSING
        self.semaphore = Semaphore(1)
        self.bots = list()

    @property
    def count(self):
        return len(set(config.bots) - set(self.bots))


locks: dict[str, Lock] = dict()
