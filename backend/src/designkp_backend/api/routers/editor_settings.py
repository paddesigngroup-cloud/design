from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from designkp_backend.db.dependencies import get_db_session
from designkp_backend.db.models.account import EditorSetting, User
from designkp_backend.services.admin_access import require_admin

router = APIRouter(prefix="/editor-settings", tags=["editor_settings"])


class SnapProfile(BaseModel):
    origin: bool = True
    corner: bool = True
    mid: bool = True
    center: bool = True
    edge: bool = True


class GeneralSettingsPayload(BaseModel):
    unit: str = "cm"
    fontFamily: str = "Tahoma"
    wallNameFontPx: int = 15


class GridSettingsPayload(BaseModel):
    meterDivisions: int = 10
    majorEvery: int = 10
    bgColor: str = "#FFFFFF"
    minorColor: str = "#E6E6E6"
    majorColor: str = "#A3A3A3"
    axisXColor: str = "#9CC9B4"
    axisYColor: str = "#BCC8EB"
    axisZColor: str = "#0000FF"


class SnapSettingsPayload(BaseModel):
    snapOn: bool = True
    snapCornerEnabled: bool = True
    snapMidEnabled: bool = True
    snapCenterEnabled: bool = True
    snapEdgeEnabled: bool = True
    wallMagnetEnabled: bool = True
    orthoEnabled: bool = True
    dimSnapProfileEnabled: bool = False
    dimSnapLineProfile: SnapProfile = Field(default_factory=SnapProfile)
    dimSnapOffsetProfile: SnapProfile = Field(default_factory=SnapProfile)


class DraftingSettingsPayload(BaseModel):
    stepDrawMode: str = "line"
    stepDrawEnabled: bool = True
    stepLineEnabled: bool = True
    stepDegreeEnabled: bool = False
    stepLineCm: float = 5
    stepAngleDeg: float = 10
    showObjectAxes: bool = False
    miterLimit: int = 10
    showGammaDebug: bool = False


class WallDefaultsPayload(BaseModel):
    wallThicknessMm: int = 120
    wallHeightMm: int = 3000
    wallFillColor: str = "#A6A6A6"
    wallEdgeColor: str = "#000000"
    wallTextColor: str = "#FFFFFF"
    wallHeightColor: str = "#4B5563"
    wall3dColor: str = "#C7CCD1"


class BeamDefaultsPayload(BaseModel):
    beamThicknessMm: int = 400
    beamHeightMm: int = 200
    beamFloorOffsetMm: int = 2600
    beamFillColor: str = "#A6A6A6"
    beamEdgeColor: str = "#000000"
    beamTextColor: str = "#FFFFFF"
    beam3dColor: str = "#C7CCD1"


class ColumnDefaultsPayload(BaseModel):
    columnWidthMm: int = 500
    columnDepthMm: int = 400
    columnHeightMm: int = 2800
    columnFillColor: str = "#A6A6A6"
    columnEdgeColor: str = "#000000"
    columnTextColor: str = "#FFFFFF"
    column3dColor: str = "#C7CCD1"


class HiddenDefaultsPayload(BaseModel):
    hiddenWallThicknessMm: float = 1
    hiddenWallColor: str = "#D8D4D4"
    hiddenWallLineWidthPx: int = 2
    hiddenWallDash: list[int] = Field(default_factory=lambda: [10, 8])


class DimensionDefaultsPayload(BaseModel):
    dimColor: str = "#E8A559"
    dimFontPx: int = 15
    dimLineWidthPx: int = 2
    dimOffsetMm: int = 150
    dimTickPx: int = 8
    dimGapTextPx: int = 6
    dimTextPadPx: int = 6
    showDimensions: bool = True


class AngleDefaultsPayload(BaseModel):
    angleColor: str = "#E8A559"
    angleFontPx: int = 12
    angleRadiusPx: int = 22
    angleArcWidthPx: int = 2


class OffsetWallSettingsPayload(BaseModel):
    offsetWallEnabled: bool = True
    offsetWallDistanceMm: int = 600
    offsetWallColor: str = "#D8D4D4"
    offsetWallLineWidthPx: int = 2
    offsetWallDash: list[int] = Field(default_factory=lambda: [10, 8])


class EditorSettingsPayload(BaseModel):
    generalSettings: GeneralSettingsPayload = Field(default_factory=GeneralSettingsPayload)
    gridSettings: GridSettingsPayload = Field(default_factory=GridSettingsPayload)
    snapSettings: SnapSettingsPayload = Field(default_factory=SnapSettingsPayload)
    draftingSettings: DraftingSettingsPayload = Field(default_factory=DraftingSettingsPayload)
    wallDefaults: WallDefaultsPayload = Field(default_factory=WallDefaultsPayload)
    beamDefaults: BeamDefaultsPayload = Field(default_factory=BeamDefaultsPayload)
    columnDefaults: ColumnDefaultsPayload = Field(default_factory=ColumnDefaultsPayload)
    hiddenDefaults: HiddenDefaultsPayload = Field(default_factory=HiddenDefaultsPayload)
    dimensionDefaults: DimensionDefaultsPayload = Field(default_factory=DimensionDefaultsPayload)
    angleDefaults: AngleDefaultsPayload = Field(default_factory=AngleDefaultsPayload)
    offsetWallSettings: OffsetWallSettingsPayload = Field(default_factory=OffsetWallSettingsPayload)


class EditorSettingsItem(EditorSettingsPayload):
    id: uuid.UUID | None = None
    admin_id: uuid.UUID
    user_id: uuid.UUID
    updated_at: datetime | None = None
    persisted: bool = False


async def _require_accessible_user(session: AsyncSession, *, admin_id: uuid.UUID, user_id: uuid.UUID) -> User:
    user = await session.scalar(
        select(User).where(
            and_(
                User.id == user_id,
                User.admin_id == admin_id,
                User.deleted_at.is_(None),
            )
        )
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found for this admin.")
    return user


def _default_payload() -> EditorSettingsPayload:
    return EditorSettingsPayload()


def _to_response(item: EditorSetting | None, *, admin_id: uuid.UUID, user_id: uuid.UUID) -> EditorSettingsItem:
    if item is None:
        default_payload = _default_payload()
        return EditorSettingsItem(
            id=None,
            admin_id=admin_id,
            user_id=user_id,
            updated_at=None,
            persisted=False,
            **default_payload.model_dump(),
        )

    normalized = EditorSettingsPayload(
        generalSettings=GeneralSettingsPayload.model_validate(item.general_settings or {}),
        gridSettings=GridSettingsPayload.model_validate(item.grid_settings or {}),
        snapSettings=SnapSettingsPayload.model_validate(item.snap_settings or {}),
        draftingSettings=DraftingSettingsPayload.model_validate(item.drafting_settings or {}),
        wallDefaults=WallDefaultsPayload.model_validate(item.wall_defaults or {}),
        beamDefaults=BeamDefaultsPayload.model_validate(item.beam_defaults or {}),
        columnDefaults=ColumnDefaultsPayload.model_validate(item.column_defaults or {}),
        hiddenDefaults=HiddenDefaultsPayload.model_validate(item.hidden_defaults or {}),
        dimensionDefaults=DimensionDefaultsPayload.model_validate(item.dimension_defaults or {}),
        angleDefaults=AngleDefaultsPayload.model_validate(item.angle_defaults or {}),
        offsetWallSettings=OffsetWallSettingsPayload.model_validate(item.offset_wall_settings or {}),
    )
    return EditorSettingsItem(
        id=item.id,
        admin_id=item.admin_id,
        user_id=item.user_id,
        updated_at=item.updated_at,
        persisted=True,
        **normalized.model_dump(),
    )


@router.get("", response_model=EditorSettingsItem)
async def get_editor_settings(
    admin_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Query(...),
    session: AsyncSession = Depends(get_db_session),
) -> EditorSettingsItem:
    await require_admin(session, admin_id)
    await _require_accessible_user(session, admin_id=admin_id, user_id=user_id)
    item = await session.scalar(
        select(EditorSetting).where(
            and_(
                EditorSetting.admin_id == admin_id,
                EditorSetting.user_id == user_id,
                EditorSetting.deleted_at.is_(None),
            )
        )
    )
    return _to_response(item, admin_id=admin_id, user_id=user_id)


@router.put("", response_model=EditorSettingsItem)
async def upsert_editor_settings(
    payload: EditorSettingsPayload,
    admin_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Query(...),
    session: AsyncSession = Depends(get_db_session),
) -> EditorSettingsItem:
    await require_admin(session, admin_id)
    await _require_accessible_user(session, admin_id=admin_id, user_id=user_id)
    item = await session.scalar(
        select(EditorSetting).where(
            and_(
                EditorSetting.admin_id == admin_id,
                EditorSetting.user_id == user_id,
            )
        )
    )
    if item is None:
        item = EditorSetting(admin_id=admin_id, user_id=user_id)
        session.add(item)

    item.deleted_at = None
    item.general_settings = payload.generalSettings.model_dump()
    item.grid_settings = payload.gridSettings.model_dump()
    item.snap_settings = payload.snapSettings.model_dump()
    item.drafting_settings = payload.draftingSettings.model_dump()
    item.wall_defaults = payload.wallDefaults.model_dump()
    item.beam_defaults = payload.beamDefaults.model_dump()
    item.column_defaults = payload.columnDefaults.model_dump()
    item.hidden_defaults = payload.hiddenDefaults.model_dump()
    item.dimension_defaults = payload.dimensionDefaults.model_dump()
    item.angle_defaults = payload.angleDefaults.model_dump()
    item.offset_wall_settings = payload.offsetWallSettings.model_dump()

    await session.commit()
    await session.refresh(item)
    return _to_response(item, admin_id=admin_id, user_id=user_id)
