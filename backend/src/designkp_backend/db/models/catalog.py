from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from designkp_backend.db.base import Base
from designkp_backend.db.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin, VersionMixin

if TYPE_CHECKING:
    from .account import Admin


class PartKind(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "part_kinds"

    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admins.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    part_kind_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True, index=True)
    part_kind_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    org_part_kind_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    admin: Mapped["Admin | None"] = relationship(back_populates="part_kinds")
    params: Mapped[list["Param"]] = relationship(back_populates="part_kind")


class ParamGroup(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "param_groups"

    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admins.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    param_group_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True, index=True)
    param_group_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    org_param_group_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    param_group_icon_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ui_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    admin: Mapped["Admin | None"] = relationship(back_populates="param_groups")
    params: Mapped[list["Param"]] = relationship(back_populates="param_group")


class Param(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "params"

    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admins.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    param_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True, index=True)
    part_kind_id: Mapped[int] = mapped_column(ForeignKey("part_kinds.part_kind_id", ondelete="RESTRICT"), nullable=False, index=True)
    param_code: Mapped[str] = mapped_column(String(64), nullable=False)
    param_title_en: Mapped[str] = mapped_column(String(255), nullable=False)
    param_title_fa: Mapped[str] = mapped_column(String(255), nullable=False)
    param_group_id: Mapped[int] = mapped_column(ForeignKey("param_groups.param_group_id", ondelete="RESTRICT"), nullable=False, index=True)
    ui_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    admin: Mapped["Admin | None"] = relationship(back_populates="params")
    part_kind: Mapped["PartKind"] = relationship(back_populates="params")
    param_group: Mapped["ParamGroup"] = relationship(back_populates="params")


class BaseFormula(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "base_formulas"

    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admins.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    fo_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True, index=True)
    param_formula: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    formula: Mapped[str] = mapped_column(String(2048), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    admin: Mapped["Admin | None"] = relationship(back_populates="base_formulas")


class PartFormula(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "part_formulas"

    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admins.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    part_formula_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True, index=True)
    part_kind_id: Mapped[int] = mapped_column(ForeignKey("part_kinds.part_kind_id", ondelete="RESTRICT"), nullable=False, index=True)
    part_sub_kind_id: Mapped[int] = mapped_column(Integer, nullable=False)
    part_code: Mapped[str] = mapped_column(String(64), nullable=False)
    part_title: Mapped[str] = mapped_column(String(255), nullable=False)
    formula_l: Mapped[str] = mapped_column(String(2048), nullable=False)
    formula_w: Mapped[str] = mapped_column(String(2048), nullable=False)
    formula_width: Mapped[str] = mapped_column(String(2048), nullable=False)
    formula_depth: Mapped[str] = mapped_column(String(2048), nullable=False)
    formula_height: Mapped[str] = mapped_column(String(2048), nullable=False)
    formula_cx: Mapped[str] = mapped_column(String(2048), nullable=False)
    formula_cy: Mapped[str] = mapped_column(String(2048), nullable=False)
    formula_cz: Mapped[str] = mapped_column(String(2048), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    admin: Mapped["Admin | None"] = relationship(back_populates="part_formulas")
    part_kind: Mapped["PartKind"] = relationship()


class Template(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "templates"

    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admins.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    temp_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True, index=True)
    temp_title: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    admin: Mapped["Admin | None"] = relationship(back_populates="templates")
    categories: Mapped[list["Category"]] = relationship(back_populates="template")


class Category(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "categories"

    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admins.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    temp_id: Mapped[int] = mapped_column(ForeignKey("templates.temp_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, index=True)
    cat_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True, index=True)
    cat_title: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    admin: Mapped["Admin | None"] = relationship(back_populates="categories")
    template: Mapped["Template"] = relationship(back_populates="categories")
