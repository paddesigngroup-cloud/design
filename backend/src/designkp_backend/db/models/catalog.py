from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from designkp_backend.db.base import Base
from designkp_backend.db.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin, VersionMixin

if TYPE_CHECKING:
    from .account import Admin, OrderDesignInteriorInstance, OrderDesignSubtractorInstance


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
    part_scope: Mapped[str] = mapped_column(String(16), nullable=False, default="structural", server_default="structural")
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
    show_in_order_attrs: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    ui_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    admin: Mapped["Admin | None"] = relationship(back_populates="param_groups")
    params: Mapped[list["Param"]] = relationship(back_populates="param_group")
    internal_part_group_links: Mapped[list["InternalPartGroupParamGroup"]] = relationship(back_populates="param_group")
    subtractor_part_group_links: Mapped[list["SubtractorPartGroupParamGroup"]] = relationship(back_populates="param_group")


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
    interior_value_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="formula", server_default="formula")
    ui_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    admin: Mapped["Admin | None"] = relationship(back_populates="params")
    part_kind: Mapped["PartKind"] = relationship(back_populates="params")
    param_group: Mapped["ParamGroup"] = relationship(back_populates="params")
    sub_category_defaults: Mapped[list["SubCategoryParamDefault"]] = relationship(back_populates="param")
    internal_part_group_defaults: Mapped[list["InternalPartGroupParamDefault"]] = relationship(back_populates="param")
    subtractor_part_group_defaults: Mapped[list["SubtractorPartGroupParamDefault"]] = relationship(back_populates="param")
    door_part_group_defaults: Mapped[list["DoorPartGroupParamDefault"]] = relationship(back_populates="param")


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
    part_model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("part_models.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
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
    lw_frame_mapping: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    part_model_side_services: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False, default=list)
    door_dependent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    admin: Mapped["Admin | None"] = relationship(back_populates="part_formulas")
    part_kind: Mapped["PartKind"] = relationship()
    part_model: Mapped["PartModel"] = relationship()


class PartService(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "part_services"

    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admins.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    service_type: Mapped[str] = mapped_column(String(255), nullable=False)
    service_description: Mapped[str] = mapped_column(Text, nullable=False)
    service_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    admin: Mapped["Admin | None"] = relationship(back_populates="part_services")


class PartServiceType(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "part_service_types"

    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admins.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    service_type: Mapped[str] = mapped_column(String(255), nullable=False)
    service_title: Mapped[str] = mapped_column(String(255), nullable=False)
    short_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    part_side: Mapped[str] = mapped_column(String(16), nullable=False, default="front", server_default="front")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    admin: Mapped["Admin | None"] = relationship(back_populates="part_service_types")


class PartModel(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "part_models"

    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admins.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    side_count: Mapped[int] = mapped_column(Integer, nullable=False)
    interior_angle_sum: Mapped[int] = mapped_column(Integer, nullable=False)
    default_angles: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    admin: Mapped["Admin | None"] = relationship(back_populates="part_models")


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
    design_outline_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#7A4A2B", server_default="#7A4A2B")
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    admin: Mapped["Admin | None"] = relationship(back_populates="categories")
    template: Mapped["Template"] = relationship(back_populates="categories")
    sub_categories: Mapped[list["SubCategory"]] = relationship(back_populates="category")


class SubCategory(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "sub_categories"

    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admins.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    temp_id: Mapped[int] = mapped_column(ForeignKey("templates.temp_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, index=True)
    cat_id: Mapped[int] = mapped_column(ForeignKey("categories.cat_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, index=True)
    sub_cat_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True, index=True)
    sub_cat_title: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    admin: Mapped["Admin | None"] = relationship(back_populates="sub_categories")
    category: Mapped["Category"] = relationship(back_populates="sub_categories")
    param_defaults: Mapped[list["SubCategoryParamDefault"]] = relationship(
        back_populates="sub_category",
        cascade="all, delete-orphan",
    )
    designs: Mapped[list["SubCategoryDesign"]] = relationship(
        back_populates="sub_category",
        cascade="all, delete-orphan",
        primaryjoin="SubCategory.id == foreign(SubCategoryDesign.sub_category_id)",
        foreign_keys="SubCategoryDesign.sub_category_id",
    )


class SubCategoryParamDefault(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "sub_category_param_defaults"

    sub_category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sub_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    param_id: Mapped[int] = mapped_column(
        ForeignKey("params.param_id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    default_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="value", server_default="value")
    binary_off_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    binary_on_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    binary_off_icon_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    binary_on_icon_path: Mapped[str | None] = mapped_column(String(255), nullable=True)

    sub_category: Mapped["SubCategory"] = relationship(back_populates="param_defaults")
    param: Mapped["Param"] = relationship(back_populates="sub_category_defaults")


class SubCategoryDesign(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "sub_category_designs"

    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admins.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    sub_category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sub_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    temp_id: Mapped[int] = mapped_column(ForeignKey("templates.temp_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, index=True)
    cat_id: Mapped[int] = mapped_column(ForeignKey("categories.cat_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, index=True)
    sub_cat_id: Mapped[int] = mapped_column(ForeignKey("sub_categories.sub_cat_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, index=True)
    design_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True, index=True)
    design_title: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    admin: Mapped["Admin | None"] = relationship()
    sub_category: Mapped["SubCategory"] = relationship(
        back_populates="designs",
        primaryjoin="foreign(SubCategoryDesign.sub_category_id) == SubCategory.id",
        foreign_keys=[sub_category_id],
    )
    parts: Mapped[list["SubCategoryDesignPart"]] = relationship(
        back_populates="design",
        cascade="all, delete-orphan",
    )
    interior_instances: Mapped[list["SubCategoryDesignInteriorInstance"]] = relationship(
        back_populates="design",
        cascade="all, delete-orphan",
    )
    subtractor_instances: Mapped[list["SubCategoryDesignSubtractorInstance"]] = relationship(
        back_populates="design",
        cascade="all, delete-orphan",
    )
    door_instances: Mapped[list["SubCategoryDesignDoorInstance"]] = relationship(
        back_populates="design",
        cascade="all, delete-orphan",
    )


class SubCategoryDesignPart(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "sub_category_design_parts"

    design_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sub_category_designs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    part_formula_id: Mapped[int] = mapped_column(
        ForeignKey("part_formulas.part_formula_id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    part_kind_id: Mapped[int] = mapped_column(
        ForeignKey("part_kinds.part_kind_id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    part_code: Mapped[str] = mapped_column(String(64), nullable=False)
    part_title: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    ui_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    design: Mapped["SubCategoryDesign"] = relationship(back_populates="parts")
    part_formula: Mapped["PartFormula"] = relationship()
    snapshots: Mapped[list["SubCategoryDesignPartSnapshot"]] = relationship(
        back_populates="design_part",
        cascade="all, delete-orphan",
    )


class SubCategoryDesignPartSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "sub_category_design_part_snapshots"

    design_part_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sub_category_design_parts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )
    resolved_params: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    resolved_base_formulas: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    resolved_part_formulas: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    width: Mapped[float | None] = mapped_column(nullable=True)
    depth: Mapped[float | None] = mapped_column(nullable=True)
    height: Mapped[float | None] = mapped_column(nullable=True)
    cx: Mapped[float | None] = mapped_column(nullable=True)
    cy: Mapped[float | None] = mapped_column(nullable=True)
    cz: Mapped[float | None] = mapped_column(nullable=True)
    viewer_payload: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)

    design_part: Mapped["SubCategoryDesignPart"] = relationship(back_populates="snapshots")


class InternalPartGroup(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "internal_part_groups"

    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admins.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    group_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True, index=True)
    group_title: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    icon_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    line_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#8A98A3", server_default="#8A98A3")
    controller_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    controller_bindings: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    admin: Mapped["Admin | None"] = relationship()
    parts: Mapped[list["InternalPartGroupItem"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )
    param_groups: Mapped[list["InternalPartGroupParamGroup"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )
    param_defaults: Mapped[list["InternalPartGroupParamDefault"]] = relationship(
        back_populates="internal_part_group",
        cascade="all, delete-orphan",
    )


class InternalPartGroupItem(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "internal_part_group_items"

    group_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("internal_part_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    part_formula_id: Mapped[int] = mapped_column(
        ForeignKey("part_formulas.part_formula_id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    part_kind_id: Mapped[int] = mapped_column(
        ForeignKey("part_kinds.part_kind_id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    part_code: Mapped[str] = mapped_column(String(64), nullable=False)
    part_title: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    ui_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    group: Mapped["InternalPartGroup"] = relationship(back_populates="parts")
    part_formula: Mapped["PartFormula"] = relationship()


class InternalPartGroupParamGroup(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "internal_part_group_param_groups"

    group_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("internal_part_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    param_group_id: Mapped[int] = mapped_column(
        ForeignKey("param_groups.param_group_id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    param_group_code: Mapped[str] = mapped_column(String(64), nullable=False)
    param_group_title: Mapped[str] = mapped_column(String(255), nullable=False)
    param_group_icon_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    ui_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    group: Mapped["InternalPartGroup"] = relationship(back_populates="param_groups")
    param_group: Mapped["ParamGroup"] = relationship(back_populates="internal_part_group_links")


class InternalPartGroupParamDefault(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "internal_part_group_param_defaults"

    internal_part_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("internal_part_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    param_id: Mapped[int] = mapped_column(
        ForeignKey("params.param_id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    default_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="value", server_default="value")
    binary_off_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    binary_on_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    binary_off_icon_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    binary_on_icon_path: Mapped[str | None] = mapped_column(String(255), nullable=True)

    internal_part_group: Mapped["InternalPartGroup"] = relationship(back_populates="param_defaults")
    param: Mapped["Param"] = relationship(back_populates="internal_part_group_defaults")


class DoorPartGroup(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "door_part_groups"

    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admins.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    group_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True, index=True)
    group_title: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    icon_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    line_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#8A98A3", server_default="#8A98A3")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    controller_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    controller_selection: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB, nullable=True)
    controller_bindings: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)

    admin: Mapped["Admin | None"] = relationship()
    parts: Mapped[list["DoorPartGroupItem"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )
    param_groups: Mapped[list["DoorPartGroupParamGroup"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )
    param_defaults: Mapped[list["DoorPartGroupParamDefault"]] = relationship(
        back_populates="door_part_group",
        cascade="all, delete-orphan",
    )


class DoorPartGroupItem(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "door_part_group_items"

    group_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("door_part_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    part_formula_id: Mapped[int] = mapped_column(
        ForeignKey("part_formulas.part_formula_id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    part_kind_id: Mapped[int] = mapped_column(
        ForeignKey("part_kinds.part_kind_id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    part_code: Mapped[str] = mapped_column(String(64), nullable=False)
    part_title: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    ui_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    group: Mapped["DoorPartGroup"] = relationship(back_populates="parts")
    part_formula: Mapped["PartFormula"] = relationship()


class DoorPartGroupParamGroup(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "door_part_group_param_groups"

    group_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("door_part_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    param_group_id: Mapped[int] = mapped_column(
        ForeignKey("param_groups.param_group_id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    param_group_code: Mapped[str] = mapped_column(String(64), nullable=False)
    param_group_title: Mapped[str] = mapped_column(String(255), nullable=False)
    param_group_icon_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    ui_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    group: Mapped["DoorPartGroup"] = relationship(back_populates="param_groups")
    param_group: Mapped["ParamGroup"] = relationship()


class DoorPartGroupParamDefault(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "door_part_group_param_defaults"

    door_part_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("door_part_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    param_id: Mapped[int] = mapped_column(
        ForeignKey("params.param_id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    default_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    door_part_group: Mapped["DoorPartGroup"] = relationship(back_populates="param_defaults")
    param: Mapped["Param"] = relationship(back_populates="door_part_group_defaults")


class SubtractorPartGroup(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "subtractor_part_groups"

    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admins.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    group_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True, index=True)
    group_title: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    icon_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    line_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#8A98A3", server_default="#8A98A3")
    controller_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    controller_bindings: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    admin: Mapped["Admin | None"] = relationship()
    parts: Mapped[list["SubtractorPartGroupItem"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )
    param_groups: Mapped[list["SubtractorPartGroupParamGroup"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )
    param_defaults: Mapped[list["SubtractorPartGroupParamDefault"]] = relationship(
        back_populates="subtractor_part_group",
        cascade="all, delete-orphan",
    )


class SubtractorPartGroupItem(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "subtractor_part_group_items"

    group_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subtractor_part_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    part_formula_id: Mapped[int] = mapped_column(
        ForeignKey("part_formulas.part_formula_id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    part_kind_id: Mapped[int] = mapped_column(
        ForeignKey("part_kinds.part_kind_id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    part_code: Mapped[str] = mapped_column(String(64), nullable=False)
    part_title: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    ui_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    group: Mapped["SubtractorPartGroup"] = relationship(back_populates="parts")
    part_formula: Mapped["PartFormula"] = relationship()


class SubtractorPartGroupParamGroup(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "subtractor_part_group_param_groups"

    group_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subtractor_part_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    param_group_id: Mapped[int] = mapped_column(
        ForeignKey("param_groups.param_group_id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    param_group_code: Mapped[str] = mapped_column(String(64), nullable=False)
    param_group_title: Mapped[str] = mapped_column(String(255), nullable=False)
    param_group_icon_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    ui_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    group: Mapped["SubtractorPartGroup"] = relationship(back_populates="param_groups")
    param_group: Mapped["ParamGroup"] = relationship(back_populates="subtractor_part_group_links")


class SubtractorPartGroupParamDefault(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "subtractor_part_group_param_defaults"

    subtractor_part_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subtractor_part_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    param_id: Mapped[int] = mapped_column(
        ForeignKey("params.param_id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    default_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="value", server_default="value")
    binary_off_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    binary_on_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    binary_off_icon_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    binary_on_icon_path: Mapped[str | None] = mapped_column(String(255), nullable=True)

    subtractor_part_group: Mapped["SubtractorPartGroup"] = relationship(back_populates="param_defaults")
    param: Mapped["Param"] = relationship(back_populates="subtractor_part_group_defaults")


class SubCategoryDesignInteriorInstance(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "sub_category_design_interior_instances"

    design_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sub_category_designs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    internal_part_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("internal_part_groups.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    instance_code: Mapped[str] = mapped_column(String(64), nullable=False)
    line_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    ui_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    placement_z: Mapped[float] = mapped_column(nullable=False, default=0)
    interior_box_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    param_values: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    param_meta: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    part_snapshots: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False, default=list)
    viewer_boxes: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", server_default="draft")

    design: Mapped["SubCategoryDesign"] = relationship(back_populates="interior_instances")
    internal_part_group: Mapped["InternalPartGroup"] = relationship()


class SubCategoryDesignDoorInstance(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "sub_category_design_door_instances"

    design_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sub_category_designs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    door_part_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("door_part_groups.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    instance_code: Mapped[str] = mapped_column(String(64), nullable=False)
    line_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    ui_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    structural_part_formula_ids: Mapped[list[int]] = mapped_column(JSONB, nullable=False, default=list)
    dependent_interior_instance_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    controller_box_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    param_values: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    param_meta: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    part_snapshots: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False, default=list)
    viewer_boxes: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", server_default="draft")

    design: Mapped["SubCategoryDesign"] = relationship(back_populates="door_instances")
    door_part_group: Mapped["DoorPartGroup"] = relationship()


class SubCategoryDesignSubtractorInstance(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, Base):
    __tablename__ = "sub_category_design_subtractor_instances"

    design_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sub_category_designs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subtractor_part_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subtractor_part_groups.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    instance_code: Mapped[str] = mapped_column(String(64), nullable=False)
    line_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    ui_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    placement_z: Mapped[float] = mapped_column(nullable=False, default=0)
    param_values: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    param_meta: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    part_snapshots: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False, default=list)
    viewer_boxes: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", server_default="draft")

    design: Mapped["SubCategoryDesign"] = relationship(back_populates="subtractor_instances")
    subtractor_part_group: Mapped["SubtractorPartGroup"] = relationship()
