import os
import shutil
from typing import Optional

from pyhocon import ConfigFactory


class Config:
    def __init__(self):
        if not os.path.exists("./kuma.conf"):
            shutil.copyfile("./example.conf", "./kuma.conf")

        self.bots: list[str] = list()

        # info
        self.version: Optional[tuple[str, str, str]] = None
        # log
        self.log_level: Optional[str] = None
        # nonebot
        self.listen_host: Optional[str] = None
        self.listen_port: Optional[int] = None
        self.token: Optional[str] = None
        # database
        self.database_url: Optional[str] = None
        # group
        self.dev_group: Optional[int] = None
        self.special_group: Optional[int] = None
        # bots
        self.nsfw_allowed: Optional[list[int]] = None
        self.auto_agree: Optional[list[int]] = None
        # diving_fish
        self.df_token: Optional[str] = None
        # lxns
        self.lx_token: Optional[str] = None
        # admin
        self.admin_accounts: Optional[list[int]] = None
        # backend
        self.backend_url: Optional[str] = None
        # llm
        self.llm_api_key: Optional[str] = None
        self.llm_model: Optional[str] = None
        self.vision_llm_model: Optional[str] = None
        self.vision_llm_prompt: Optional[str] = None
        # tts
        self.tts_api_key: Optional[str] = None
        self.tts_model: Optional[str] = None
        self.tts_voice_id: Optional[str] = None

        # 解析配置文件
        self.read_config()

    def read_config(self):
        data = ConfigFactory.parse_file("./kuma.conf")
        self.version = data["info"]["version"]
        self.log_level = data["log"]["log_level"]
        self.listen_host = data["nonebot"]["listen_host"]
        self.listen_port = data["nonebot"]["listen_port"]
        self.token = data["nonebot"]["token"]
        self.database_url = data["database"]["url"]
        self.dev_group = data["group"]["dev"]
        self.special_group = data["group"]["special"]
        self.nsfw_allowed = data["bots"]["nsfw_allowed"]
        self.auto_agree = data["bots"]["auto_agree"]
        self.df_token = data["prober"]["diving_fish_token"]
        self.lx_token = data["prober"]["lxns_token"]
        self.admin_accounts = data["admin"]["accounts"]
        self.backend_url = data["backend"]["url"]
        self.llm_api_key = data["llm"]["api_key"]
        self.llm_model = data["llm"]["model"]
        self.vision_llm_model = data["llm"]["vision"]["model"]
        self.vision_llm_prompt = data["llm"]["vision"]["prompt"]
        self.tts_api_key = data["tts"]["api_key"]
        self.tts_model = data["tts"]["model"]
        self.tts_voice_id = data["tts"]["voice_id"]


config = Config()
