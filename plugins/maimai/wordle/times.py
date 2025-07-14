import shelve
from datetime import date, timedelta

from dill import Pickler, Unpickler

shelve.Pickler = Pickler
shelve.Unpickler = Unpickler


class Times(object):
    def __init__(self):
        self.data_path = "./data/wordle_times.db"

    def add(
        self,
        user_id: str,
        year: int,
        month: int,
        day: int,
    ) -> None:
        obj = {
            "year": year,
            "month": month,
            "day": day,
        }
        with shelve.open(self.data_path) as data:
            if user_id in data:
                times_data = data[user_id]
                times_data.insert(0, obj)
                data[user_id] = times_data
                return

            data.setdefault(user_id, [obj])

    def check_available(self, user_id: str) -> bool:
        with shelve.open(self.data_path) as data:
            if user_id not in data:
                return False

            today = date.today()
            times = 0

            for times_data in data[user_id]:
                _date = date(**times_data)
                if today - date(**times_data) < timedelta(days=7):
                    today = _date
                    times += 1
                    if times > 9:
                        return True

        return False


times = Times()
