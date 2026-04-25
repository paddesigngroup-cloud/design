from __future__ import annotations

import csv
import io
import secrets
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool

from designkp_backend.config import get_settings


TABLE_FILE_NAMES = {
    "part_kinds": "part_kinds.csv",
    "part_services": "part_services.csv",
    "service_types": "service_types.csv",
    "param_groups": "param_groups.csv",
    "params": "params.csv",
    "base_formulas": "base_formulas.csv",
    "part_formulas": "part_formulas.csv",
    "templates": "templates.csv",
    "categories": "categories.csv",
    "sub_categories": "sub_categories.csv",
    "orders": "orders.csv",
}

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
STAGED_ICON_PREFIX = "staged-"


def _admin_root(admin_id: uuid.UUID) -> Path:
    return get_settings().admin_storage_root_path / str(admin_id)


def ensure_admin_storage(admin_id: uuid.UUID) -> dict[str, Path]:
    root = _admin_root(admin_id)
    paths = {
        "root": root,
        "tables": root / "tables",
        "icons": root / "icons",
        "orders": root / "orders",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def write_table_snapshot(admin_id: uuid.UUID, table_name: str, headers: list[str], rows: list[list[object]]) -> Path:
    paths = ensure_admin_storage(admin_id)
    file_name = TABLE_FILE_NAMES.get(table_name, f"{table_name}.csv")
    target = paths["tables"] / file_name
    with target.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        writer.writerows(rows)
    return target


async def write_table_snapshot_async(admin_id: uuid.UUID, table_name: str, headers: list[str], rows: list[list[object]]) -> Path:
    return await run_in_threadpool(write_table_snapshot, admin_id, table_name, headers, rows)


def csv_bytes(headers: list[str], rows: list[list[object]]) -> bytes:
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(headers)
    writer.writerows(rows)
    return ("\ufeff" + stream.getvalue()).encode("utf-8")


def _safe_slug(value: str) -> str:
    text = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    text = "-".join(part for part in text.split("-") if part)
    return text[:48] or "item"


def normalize_icon_file_name(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    # Accept legacy stored API paths but keep only the final safe file name in DB/export.
    return Path(text.split("?", 1)[0]).name or None


def is_staged_icon_file_name(value: str | None) -> bool:
    file_name = normalize_icon_file_name(value)
    return bool(file_name and file_name.startswith(STAGED_ICON_PREFIX))


def _icon_target_path(admin_id: uuid.UUID, file_name: str | None) -> Path | None:
    safe_name = normalize_icon_file_name(file_name)
    if not safe_name:
        return None
    return ensure_admin_storage(admin_id)["icons"] / safe_name


def _validate_and_normalize_icon(raw: bytes):
    try:
        from PIL import Image, ImageOps
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Image processing dependency is not installed on the server.",
        ) from exc

    settings = get_settings()
    try:
        with Image.open(io.BytesIO(raw)) as image:
            return ImageOps.fit(
                image.convert("RGBA"),
                (settings.param_group_icon_size_px, settings.param_group_icon_size_px),
                method=Image.Resampling.LANCZOS,
            )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is not a valid image.") from exc


async def save_param_group_icon(admin_id: uuid.UUID, file: UploadFile, *, slug_hint: str) -> tuple[str, Path]:
    settings = get_settings()
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only png, jpg, jpeg, or webp files are allowed.",
        )

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")
    if len(raw) > settings.max_icon_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Icon file is too large.")
    return await run_in_threadpool(_save_param_group_icon_sync, admin_id, raw, slug_hint)


def _save_param_group_icon_sync(admin_id: uuid.UUID, raw: bytes, slug_hint: str) -> tuple[str, Path]:
    normalized = _validate_and_normalize_icon(raw)
    paths = ensure_admin_storage(admin_id)
    file_name = f"{STAGED_ICON_PREFIX}{_safe_slug(slug_hint)}-{secrets.token_hex(6)}.webp"
    target = paths["icons"] / file_name
    normalized.save(target, format="WEBP", quality=92, method=6)
    final_target = paths["icons"] / file_name[len(STAGED_ICON_PREFIX) :]
    normalized.save(final_target, format="WEBP", quality=92, method=6)
    return file_name, target


def discard_staged_icon(admin_id: uuid.UUID, file_name: str | None) -> None:
    normalized = normalize_icon_file_name(file_name)
    if not normalized or not is_staged_icon_file_name(normalized):
        return
    target = ensure_admin_storage(admin_id)["icons"] / normalized
    if target.exists() and target.parent == ensure_admin_storage(admin_id)["icons"]:
        target.unlink(missing_ok=True)


def discard_all_staged_icons(admin_id: uuid.UUID) -> int:
    icons_dir = ensure_admin_storage(admin_id)["icons"]
    removed = 0
    for path in icons_dir.glob(f"{STAGED_ICON_PREFIX}*"):
        if path.is_file() and path.parent == icons_dir:
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def delete_final_icon(admin_id: uuid.UUID, file_name: str | None) -> None:
    normalized = normalize_icon_file_name(file_name)
    if not normalized:
        return
    target = ensure_admin_storage(admin_id)["icons"] / normalized
    if target.exists() and target.parent == ensure_admin_storage(admin_id)["icons"]:
        target.unlink(missing_ok=True)


def finalize_param_group_icon(admin_id: uuid.UUID, file_name: str | None, *, previous_file_name: str | None = None) -> str | None:
    normalized = normalize_icon_file_name(file_name)
    previous_normalized = normalize_icon_file_name(previous_file_name)
    if not normalized:
        if previous_normalized:
            delete_final_icon(admin_id, previous_normalized)
        return None

    if is_staged_icon_file_name(normalized):
        paths = ensure_admin_storage(admin_id)
        source = paths["icons"] / normalized
        final_name = normalized[len(STAGED_ICON_PREFIX) :]
        target = paths["icons"] / final_name
        if not source.exists():
            fallback_target = paths["icons"] / final_name
            if fallback_target.exists() and fallback_target.parent == paths["icons"]:
                if previous_normalized and previous_normalized != final_name:
                    delete_final_icon(admin_id, previous_normalized)
                return final_name
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Uploaded icon draft not found.")
        if previous_normalized and previous_normalized != final_name:
            delete_final_icon(admin_id, previous_normalized)
        if source.exists():
            source.unlink(missing_ok=True)
        return final_name

    if previous_normalized and previous_normalized != normalized:
        delete_final_icon(admin_id, previous_normalized)
    return normalized


def resolve_admin_icon_path(admin_id: uuid.UUID, file_name: str) -> Path:
    safe_name = Path(file_name).name
    target = ensure_admin_storage(admin_id)["icons"] / safe_name
    if not target.exists() and safe_name.startswith(STAGED_ICON_PREFIX):
        fallback_target = ensure_admin_storage(admin_id)["icons"] / safe_name[len(STAGED_ICON_PREFIX) :]
        if fallback_target.exists() and fallback_target.parent == ensure_admin_storage(admin_id)["icons"]:
            return fallback_target
    if not target.exists() or target.parent != ensure_admin_storage(admin_id)["icons"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Icon file not found.")
    return target


def admin_icon_exists(admin_id: uuid.UUID, file_name: str | None) -> bool:
    target = _icon_target_path(admin_id, file_name)
    if target is None:
        return False
    if target.exists() and target.parent == ensure_admin_storage(admin_id)["icons"]:
        return True
    safe_name = normalize_icon_file_name(file_name)
    if safe_name and safe_name.startswith(STAGED_ICON_PREFIX):
        fallback_target = _icon_target_path(admin_id, safe_name[len(STAGED_ICON_PREFIX) :])
        return bool(fallback_target and fallback_target.exists() and fallback_target.parent == ensure_admin_storage(admin_id)["icons"])
    return False
