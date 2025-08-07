from nonebot.adapters import Bot
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent
from nonebot.permission import Permission

from .Config import config


class Admin:
    __slots__ = ()

    def __repr__(self) -> str:
        return "Admin()"

    async def __call__(self, bot: Bot, event: MessageEvent) -> bool:
        return event.user_id in config.admin_accounts


class GroupManager:
    __slots__ = ()

    def __repr__(self) -> str:
        return "GroupManager()"

    async def __call__(self, bot: Bot, event: GroupMessageEvent) -> bool:
        return event.sender.role == "owner" or event.sender.role == "admin"


ADMIN: Permission = Permission(Admin())
GROUP_MANAGER: Permission = Permission(GroupManager())
