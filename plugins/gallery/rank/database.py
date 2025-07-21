import datetime
import shelve

from dill import Pickler, Unpickler

shelve.Pickler = Pickler
shelve.Unpickler = Unpickler


class Ranking(object):
    def __init__(self):
        self.data_path = "./data/gallery_ranking/"
        self.pic_path = "./Static/Gallery/SFW/"
        self.nsfw_pic_path = "./Static/Gallery/NSFW/"

    @property
    def now(self):
        today = datetime.date.today()

        # 获取当前年份
        year = today.year

        # 获取当前日期所在的周数
        week_number = today.isocalendar()[1]

        # 将年份和周数拼接成字符串
        result = str(year) + str(week_number)
        return result

    def gen_rank(self, time):
        leaderboard = list()

        with shelve.open(f"{self.data_path}{time}.db") as data:
            for qq, qq_data in data.items():
                total_count = qq_data["sfw"] + qq_data["nsfw"] + qq_data["video"]
                leaderboard.append((qq, total_count))

        leaderboard.sort(key=lambda x: x[1], reverse=True)

        return leaderboard[:5]

    def update_count(self, qq: str, type: str):
        time = self.now

        with shelve.open(f"{self.data_path}{time}.db") as count_data:
            if qq not in count_data:
                count = count_data.setdefault(qq, {"sfw": 0, "nsfw": 0, "video": 0})
            else:
                count = count_data[qq]

            count[type] += 1
            count_data[qq] = count


ranking = Ranking()
