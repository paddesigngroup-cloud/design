from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from designkp_backend.services.order_designs import (
    SNAPSHOT_META_KEY,
    build_order_design_snapshot_checksum,
    next_order_design_instance_code,
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
