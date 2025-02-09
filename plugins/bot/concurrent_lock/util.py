from asyncio import Semaphore
from enum import Enum, unique


@unique
class States(Enum):
    PROCESSING = 0
    PROCESSED = 1
    SKIPED = 2
    NEED_TO_SWITCH = 3


class Lock(object):
    def __init__(self):
        self.state = States.PROCESSING
        self.semaphore = Semaphore()
        self.count = 0


locks: dict[int, Lock] = dict()
