from enum import Enum, unique

from anyio import Semaphore


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
        self.count = 0


locks: dict[int, Lock] = dict()
