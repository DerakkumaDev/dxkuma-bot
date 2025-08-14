from typing import Any

from sqlalchemy import String, Boolean
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import Mapped, mapped_column

from util.database import Base, with_transaction


class UserConfig(Base):
    __tablename__ = "user_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(10), unique=True, nullable=False, index=True
    )
    frame: Mapped[str] = mapped_column(String(6), default="200502")
    plate: Mapped[str] = mapped_column(String(6), default="101")
    icon: Mapped[str] = mapped_column(String(6), default="101")
    rating_tj: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(16), default="lxns")
    lx_personal_token: Mapped[str] = mapped_column(String(44), nullable=True)
    allow_other: Mapped[bool] = mapped_column(Boolean, default=True)


class UserConfigManager:
    @with_transaction
    async def get_user_config(self, user_id: str, **kwargs) -> dict:
        session: AsyncSession = kwargs["session"]

        stmt = select(UserConfig).where(UserConfig.user_id == user_id)
        result = await session.execute(stmt)
        config = result.scalar_one_or_none()

        if config:
            return {
                "frame": config.frame,
                "plate": config.plate,
                "icon": config.icon,
                "rating_tj": config.rating_tj,
                "source": config.source,
                "lx_personal_token": config.lx_personal_token,
                "allow_other": config.allow_other,
            }

        return {
            "frame": "200502",
            "plate": "101",
            "icon": "101",
            "rating_tj": True,
            "source": "lxns",
            "lx_personal_token": None,
            "allow_other": True,
        }

    @with_transaction
    async def set_user_config(self, user_id: str, config_data: dict, **kwargs) -> None:
        session: AsyncSession = kwargs["session"]

        default_config = {
            "frame": "200502",
            "plate": "101",
            "icon": "101",
            "rating_tj": True,
            "source": "lxns",
            "lx_personal_token": None,
            "allow_other": True,
        }
        merged_config = {**default_config, **config_data}
        merged_config["user_id"] = user_id

        stmt = insert(UserConfig).values(**merged_config)
        update_dict = {key: stmt.excluded[key] for key in config_data.keys()}

        stmt = stmt.on_conflict_do_update(index_elements=["user_id"], set_=update_dict)
        await session.execute(stmt)

    @with_transaction
    async def get_config_value(
        self, user_id: str, key: str, default=None, **kwargs
    ) -> Any:
        session: AsyncSession = kwargs["session"]

        stmt = select(UserConfig).where(UserConfig.user_id == user_id)
        result = await session.execute(stmt)
        config = result.scalar_one_or_none()

        if config and hasattr(config, key):
            return getattr(config, key)

        return default

    @with_transaction
    async def set_config_value(
        self, user_id: str, key: str, value: Any, **kwargs
    ) -> bool:
        session: AsyncSession = kwargs["session"]

        stmt = select(UserConfig).where(UserConfig.user_id == user_id)
        result = await session.execute(stmt)
        config = result.scalar_one_or_none()

        if config and hasattr(config, key) and getattr(config, key) == value:
            return False

        default_config = {
            "frame": "200502",
            "plate": "101",
            "icon": "101",
            "rating_tj": True,
            "source": "lxns",
            "lx_personal_token": None,
            "allow_other": True,
        }
        default_config[key] = value
        default_config["user_id"] = user_id

        stmt = insert(UserConfig).values(**default_config)
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id"], set_={key: stmt.excluded[key]}
        )
        await session.execute(stmt)
        return True


user_config_manager = UserConfigManager()
