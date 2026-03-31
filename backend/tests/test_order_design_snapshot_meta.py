from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from designkp_backend.api.routers import order_designs as order_designs_router
from designkp_backend.services.order_designs import (
    SNAPSHOT_META_KEY,
    build_order_design_snapshot_checksum,
    next_order_design_instance_code,
    order_design_snapshot_looks_fresh,
    order_design_snapshot_marker,
    read_order_design_snapshot_checksum,
    strip_snapshot_state_from_meta,
    with_order_design_snapshot_checksum,
)


def _source_design() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        version_id=7,
        updated_at=datetime(2026, 3, 26, 12, 0, tzinfo=timezone.utc),
    )


def test_snapshot_meta_helpers_round_trip() -> None:
    raw_meta = {
        "width": {"input_mode": "value"},
        SNAPSHOT_META_KEY: {"version": 1, "checksum": "old"},
    }
    cleaned = strip_snapshot_state_from_meta(raw_meta)
    assert SNAPSHOT_META_KEY not in cleaned

    updated = with_order_design_snapshot_checksum(cleaned, checksum="new-checksum")
    assert read_order_design_snapshot_checksum(updated) == "new-checksum"


def test_snapshot_freshness_uses_marker_and_checksum() -> None:
    source = _source_design()
    interior = SimpleNamespace(
        id=uuid4(),
        version_id=3,
        updated_at=datetime(2026, 3, 31, 9, 0, tzinfo=timezone.utc),
        internal_part_group_id=uuid4(),
        instance_code="inner-01",
        ui_order=1,
        placement_z=1.0,
        param_values={"k": "2"},
    )
    checksum = build_order_design_snapshot_checksum(
        source_design=source,
        order_attr_values={"width": "200"},
        interior_instances=[interior],
        source_state={"signature": "sig-a"},
    )
    marker = order_design_snapshot_marker(
        source_design=source,
        interior_instances=[interior],
    )
    meta = with_order_design_snapshot_checksum({}, checksum=checksum, marker=marker, source_state_signature="sig-a")

    assert order_design_snapshot_looks_fresh(
        meta=meta,
        snapshot_checksum=checksum,
        source_design=source,
        interior_instances=[interior],
    ) is True

    changed_payload = dict(interior.__dict__)
    changed_payload["version_id"] = 4
    changed_interior = SimpleNamespace(**changed_payload)
    assert order_design_snapshot_looks_fresh(
        meta=meta,
        snapshot_checksum=checksum,
        source_design=source,
        interior_instances=[changed_interior],
    ) is False


def test_checksum_is_stable_for_reordered_inputs() -> None:
    source = _source_design()
    interior_a = SimpleNamespace(
        id=uuid4(),
        internal_part_group_id=uuid4(),
        instance_code="B",
        ui_order=2,
        placement_z=3.0,
        param_values={"z": "9", "a": "1"},
    )
    interior_b = SimpleNamespace(
        id=uuid4(),
        internal_part_group_id=uuid4(),
        instance_code="A",
        ui_order=1,
        placement_z=1.0,
        param_values={"k": "2"},
    )

    checksum_1 = build_order_design_snapshot_checksum(
        source_design=source,
        order_attr_values={"height": "100", "width": "200"},
        interior_instances=[interior_a, interior_b],
    )
    checksum_2 = build_order_design_snapshot_checksum(
        source_design=source,
        order_attr_values={"width": "200", "height": "100"},
        interior_instances=[interior_b, interior_a],
    )

    assert checksum_1 == checksum_2


def test_checksum_changes_when_source_state_changes() -> None:
    source = _source_design()
    interior = SimpleNamespace(
        id=uuid4(),
        internal_part_group_id=uuid4(),
        instance_code="A",
        ui_order=1,
        placement_z=1.0,
        param_values={"k": "2"},
    )
    checksum_1 = build_order_design_snapshot_checksum(
        source_design=source,
        order_attr_values={"width": "200"},
        interior_instances=[interior],
        source_state={"signature": "sig-a"},
    )
    checksum_2 = build_order_design_snapshot_checksum(
        source_design=source,
        order_attr_values={"width": "200"},
        interior_instances=[interior],
        source_state={"signature": "sig-b"},
    )

    assert checksum_1 != checksum_2


class _FakeScalarResult:
    def __init__(self, values: list[str]) -> None:
        self._values = values

    def all(self) -> list[str]:
        return list(self._values)


class _FakeSession:
    def __init__(self, values: list[str]) -> None:
        self._values = values

    async def scalars(self, _stmt: object) -> _FakeScalarResult:
        return _FakeScalarResult(self._values)


def test_next_order_design_instance_code_uses_u_sequence() -> None:
    session = _FakeSession(["U1", "legacy-01", "U2", "u10", "Z4", "Uxyz"])
    result = asyncio.run(
        next_order_design_instance_code(
            session,
            order_id=uuid4(),
            design_code="z1",
        )
    )

    assert result == "U11"


def test_next_order_design_instance_code_starts_from_u1_when_no_matching_rows() -> None:
    session = _FakeSession(["z1-01", "A2", ""])
    result = asyncio.run(
        next_order_design_instance_code(
            session,
            order_id=uuid4(),
            design_code="z1",
        )
    )

    assert result == "U1"


class _FakeDuplicateSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.created_order_design = None

    def add(self, item: object) -> None:
        self.added.append(item)
        if item.__class__.__name__ == "OrderDesign":
            self.created_order_design = item

    async def flush(self) -> None:
        if self.created_order_design is not None and getattr(self.created_order_design, "id", None) is None:
            self.created_order_design.id = uuid4()

    async def commit(self) -> None:
        return None


def test_duplicate_order_design_record_clones_full_payload(monkeypatch) -> None:
    source_order_id = uuid4()
    source_design_id = uuid4()
    source_sub_category_id = uuid4()
    source_admin_id = uuid4()
    source_user_id = uuid4()
    source_snapshot_checksum = "checksum-123"
    source_order_attr_values = {"width": "1200"}
    source_order_attr_meta = {
        "width": {"label": "عرض"},
        SNAPSHOT_META_KEY: {"version": 1, "checksum": source_snapshot_checksum},
    }
    source_part_snapshots = [{"part_code": "A", "viewer": {"x": 1}}]
    source_viewer_boxes = [{"x": 10, "children": [{"y": 20}]}]
    source_interior_instances = [
        SimpleNamespace(
            source_instance_id=uuid4(),
            internal_part_group_id=uuid4(),
            instance_code="inner-01",
            ui_order=1,
            placement_z=15.0,
            interior_box_snapshot={"box": {"w": 1}},
            param_values={"depth": "550"},
            param_meta={"depth": {"label": "عمق"}},
            part_snapshots=[{"part_code": "inner-A"}],
            viewer_boxes=[{"x": 2}],
            status="draft",
        )
    ]
    source_item = SimpleNamespace(
        id=uuid4(),
        order_id=source_order_id,
        admin_id=source_admin_id,
        user_id=source_user_id,
        sub_category_design_id=source_design_id,
        sub_category_id=source_sub_category_id,
        design_code="z1",
        design_title="طرح مبدا",
        instance_code="U4",
        sort_order=4,
        status="draft",
        order_attr_values=source_order_attr_values,
        order_attr_meta=source_order_attr_meta,
        part_snapshots=source_part_snapshots,
        viewer_boxes=source_viewer_boxes,
        snapshot_checksum=source_snapshot_checksum,
        interior_instances=source_interior_instances,
    )
    session = _FakeDuplicateSession()

    async def _interior_ready(_session):
        return True

    async def _require_order(_session, *, order_id):
        return SimpleNamespace(id=order_id)

    async def _next_instance_code(_session, *, order_id, design_code):
        return "U5"

    async def _next_sort_order(_session, *, order_id):
        return 5

    async def _ensure_unique(_session, *, order_id, instance_code, exclude_id=None):
        return None

    async def _require_item(_session, item_id):
        return session.created_order_design

    monkeypatch.setattr(order_designs_router, "interior_instance_tables_ready", _interior_ready)
    monkeypatch.setattr(order_designs_router, "require_accessible_order", _require_order)
    monkeypatch.setattr(order_designs_router, "next_order_design_instance_code", _next_instance_code)
    monkeypatch.setattr(order_designs_router, "next_order_design_sort_order", _next_sort_order)
    monkeypatch.setattr(order_designs_router, "_ensure_unique_instance_code", _ensure_unique)
    monkeypatch.setattr(order_designs_router, "_require_item", _require_item)

    duplicated = asyncio.run(
        order_designs_router._duplicate_order_design_record(
            session,
            source_item=source_item,
        )
    )

    assert duplicated is session.created_order_design
    assert duplicated.instance_code == "U5"
    assert duplicated.design_title == source_item.design_title
    assert duplicated.design_code == source_item.design_code
    assert duplicated.sort_order == 5
    assert duplicated.snapshot_checksum == source_snapshot_checksum
    assert duplicated.order_attr_values == source_order_attr_values
    assert duplicated.order_attr_values is not source_order_attr_values
    assert duplicated.part_snapshots == source_part_snapshots
    assert duplicated.part_snapshots is not source_part_snapshots
    assert duplicated.viewer_boxes == source_viewer_boxes
    assert duplicated.viewer_boxes is not source_viewer_boxes
    assert duplicated.order_attr_meta["width"] == {"label": "عرض"}
    assert read_order_design_snapshot_checksum(duplicated.order_attr_meta) == source_snapshot_checksum

    duplicated.order_attr_values["width"] = "1300"
    duplicated.part_snapshots[0]["viewer"]["x"] = 99
    duplicated.viewer_boxes[0]["children"][0]["y"] = 88

    assert source_order_attr_values["width"] == "1200"
    assert source_part_snapshots[0]["viewer"]["x"] == 1
    assert source_viewer_boxes[0]["children"][0]["y"] == 20

    duplicated_interiors = [item for item in session.added if item.__class__.__name__ == "OrderDesignInteriorInstance"]
    assert len(duplicated_interiors) == 1
    assert duplicated_interiors[0].order_design_id == duplicated.id
    assert duplicated_interiors[0].instance_code == "inner-01"
    assert duplicated_interiors[0].param_values == {"depth": "550"}
    assert duplicated_interiors[0].param_values is not source_interior_instances[0].param_values
