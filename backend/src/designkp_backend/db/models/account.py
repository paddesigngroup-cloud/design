from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, ForeignKeyConstraint, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from designkp_backend.db.base import Base
from designkp_backend.db.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin, VersionMixin

if TYPE_CHECKING:
    from .catalog import PartKind


class SuperAdmin(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "super_admins"

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class Admin(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "admins"

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    users: Mapped[list["User"]] = relationship(
        back_populates="admin",
        cascade="all, delete-orphan",
    )
    orders: Mapped[list["Order"]] = relationship(
        back_populates="admin",
        foreign_keys="Order.admin_id",
    )
    part_kinds: Mapped[list["PartKind"]] = relationship(
        back_populates="admin",
    )


class User(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("id", "admin_id", name="uq_users_id_admin_id"),
    )

    admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admins.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    admin: Mapped[Admin] = relationship(back_populates="users")
    orders: Mapped[list["Order"]] = relationship(
        back_populates="user",
        foreign_keys="Order.user_id",
    )


class Order(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "admin_id"],
            ["users.id", "users.admin_id"],
            name="fk_orders_user_id_admin_id_users",
            ondelete="RESTRICT",
        ),
    )

    order_number: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admins.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("timezone('utc', now())"),
    )

    admin: Mapped[Admin] = relationship(back_populates="orders", foreign_keys=[admin_id])
    user: Mapped[User] = relationship(back_populates="orders", foreign_keys=[user_id])
