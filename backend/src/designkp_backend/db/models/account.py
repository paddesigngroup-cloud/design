from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, ForeignKeyConstraint, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from designkp_backend.db.base import Base
from designkp_backend.db.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin, VersionMixin

if TYPE_CHECKING:
    from .catalog import BaseFormula, Category, InternalPartGroup, Param, ParamGroup, PartFormula, PartKind, SubCategory, SubCategoryDesign, SubCategoryDesignInteriorInstance, Template


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
    order_drawings: Mapped[list["OrderDrawing"]] = relationship(
        back_populates="admin",
        foreign_keys="OrderDrawing.admin_id",
    )
    order_designs: Mapped[list["OrderDesign"]] = relationship(
        back_populates="admin",
        foreign_keys="OrderDesign.admin_id",
    )
    part_kinds: Mapped[list["PartKind"]] = relationship(
        back_populates="admin",
    )
    param_groups: Mapped[list["ParamGroup"]] = relationship(
        back_populates="admin",
    )
    params: Mapped[list["Param"]] = relationship(
        back_populates="admin",
    )
    base_formulas: Mapped[list["BaseFormula"]] = relationship(
        back_populates="admin",
    )
    part_formulas: Mapped[list["PartFormula"]] = relationship(
        back_populates="admin",
    )
    templates: Mapped[list["Template"]] = relationship(
        back_populates="admin",
    )
    categories: Mapped[list["Category"]] = relationship(
        back_populates="admin",
    )
    sub_categories: Mapped[list["SubCategory"]] = relationship(
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
    order_drawings: Mapped[list["OrderDrawing"]] = relationship(
        back_populates="user",
        foreign_keys="OrderDrawing.user_id",
    )
    order_designs: Mapped[list["OrderDesign"]] = relationship(
        back_populates="user",
        foreign_keys="OrderDesign.user_id",
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
        UniqueConstraint("admin_id", "order_number", name="uq_orders_admin_order_number"),
    )

    order_name: Mapped[str] = mapped_column(String(255), nullable=False)
    order_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", server_default="draft")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    drawing: Mapped["OrderDrawing | None"] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        uselist=False,
    )
    order_designs: Mapped[list["OrderDesign"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )


class OrderDrawing(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "order_drawings"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_order_drawings_order_id"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
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
    drawing_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    walls_count: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    hidden_walls_count: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    dimensions_count: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    beams_count: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    columns_count: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")

    order: Mapped[Order] = relationship(back_populates="drawing")
    admin: Mapped[Admin] = relationship(back_populates="order_drawings", foreign_keys=[admin_id])
    user: Mapped[User] = relationship(back_populates="order_drawings", foreign_keys=[user_id])


class OrderDesign(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "order_designs"
    __table_args__ = (
        UniqueConstraint("order_id", "instance_code", name="uq_order_designs_order_instance_code"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
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
    sub_category_design_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sub_category_designs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sub_category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sub_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    design_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    design_title: Mapped[str] = mapped_column(String(255), nullable=False)
    instance_code: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", server_default="draft")
    order_attr_values: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    order_attr_meta: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    part_snapshots: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False, default=list)
    viewer_boxes: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False, default=list)
    snapshot_checksum: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="")

    order: Mapped[Order] = relationship(back_populates="order_designs")
    admin: Mapped[Admin] = relationship(back_populates="order_designs", foreign_keys=[admin_id])
    user: Mapped[User] = relationship(back_populates="order_designs", foreign_keys=[user_id])
    sub_category_design: Mapped["SubCategoryDesign"] = relationship()
    interior_instances: Mapped[list["OrderDesignInteriorInstance"]] = relationship(
        back_populates="order_design",
        cascade="all, delete-orphan",
    )


class OrderDesignInteriorInstance(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "order_design_interior_instances"

    order_design_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("order_designs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_instance_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sub_category_design_interior_instances.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    internal_part_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("internal_part_groups.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    instance_code: Mapped[str] = mapped_column(String(64), nullable=False)
    ui_order: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    placement_z: Mapped[float] = mapped_column(nullable=False, default=0)
    interior_box_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    param_values: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    param_meta: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    part_snapshots: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False, default=list)
    viewer_boxes: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", server_default="draft")

    order_design: Mapped["OrderDesign"] = relationship(back_populates="interior_instances")
    source_instance: Mapped["SubCategoryDesignInteriorInstance | None"] = relationship()
    internal_part_group: Mapped["InternalPartGroup"] = relationship()
