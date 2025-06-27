import nonebot
from nonebot.adapters.onebot import V11Adapter

from util.Config import config

if __name__ == "__main__":
    with open(".env", "w", encoding="utf-8") as v:
        file = (
            f"DRIVER=~fastapi\n"
            f"HOST={config.listen_host}\n"
            f"PORT={config.listen_port}\n"
            f"ONEBOT_ACCESS_TOKEN={config.token}\n"
            f"LOG_LEVEL={config.log_level}"
        )
        v.write(file)
        v.close()

    nonebot.init()

    driver = nonebot.get_driver()
    driver.register_adapter(V11Adapter)

    nonebot.load_plugins("plugins/bot")
    nonebot.load_plugins("plugins/maimai")

    nonebot.run()
