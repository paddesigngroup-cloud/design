from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

from designkp_backend.api.routers import order_designs as order_router
from designkp_backend.api.routers import sub_category_designs as subcat_router


class _FakeMutationSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.flush_count = 0
        self.commit_count = 0

    def add(self, item: object) -> None:
        self.added.append(item)

    async def delete(self, item: object) -> None:
        self.deleted.append(item)

    async def flush(self) -> None:
        self.flush_count += 1
        for item in self.added:
            if getattr(item, "id", None) is None:
                item.id = uuid4()

    async def commit(self) -> None:
        self.commit_count += 1


class _FakeScalarSession:
    def __init__(self, item: object) -> None:
        self.item = item
        self.scalar_calls = 0
        self.commit_count = 0

    async def scalar(self, _stmt: object) -> object:
        self.scalar_calls += 1
        return self.item

    async def commit(self) -> None:
        self.commit_count += 1


def test_subcategory_add_refreshes_only_target_instance(monkeypatch) -> None:
    design_id = uuid4()
    design = SimpleNamespace(
        id=design_id,
        admin_id=uuid4(),
        sub_category_id=uuid4(),
        interior_instances=[],
    )
    session = _FakeMutationSession()
    refresh_calls: list[str] = []

    async def fake_interior_ready(_session) -> bool:
        return True

    async def fake_next_state(_session, **_kwargs):
        return "inner-01", 0, {"width": 10}, {"depth": "550"}, {"depth": {"label": "عمق"}}

    async def fake_load_design(_session, _design_uuid):
        for item in session.added:
            if item not in design.interior_instances:
                design.interior_instances.append(item)
        return design

    async def fake_refresh(_session, *, design, instance):
        refresh_calls.append(str(instance.id))
        instance.part_snapshots = [{"part_code": "inner-A"}]
        instance.viewer_boxes = [{"width": 10}]
        instance.status = "draft"

    class _FakeInteriorInstance:
        def __init__(self, **kwargs) -> None:
            for key, value in kwargs.items():
                setattr(self, key, value)
            self.id = None
            self.part_snapshots = []
            self.viewer_boxes = []
            self.status = "draft"

    monkeypatch.setattr(subcat_router, "interior_instance_tables_ready", fake_interior_ready)
    monkeypatch.setattr(subcat_router, "_next_interior_instance_state", fake_next_state)
    monkeypatch.setattr(subcat_router, "_load_design", fake_load_design)
    monkeypatch.setattr(subcat_router, "_refresh_design_interior_instance", fake_refresh)
    monkeypatch.setattr(subcat_router, "SubCategoryDesignInteriorInstance", _FakeInteriorInstance)

    payload = subcat_router.SubCategoryDesignInteriorInstanceCreate(
        internal_part_group_id=uuid4(),
        placement_z=0,
        param_values={},
    )
    created = asyncio.run(
        subcat_router.create_sub_category_design_interior_instance(
            design_id,
            payload,
            session,
        )
    )

    assert created.instance_code == "inner-01"
    assert created.param_values == {"depth": "550"}
    assert len(refresh_calls) == 1
    assert len(session.added) == 1
    assert session.commit_count == 1


def test_subcategory_delete_stays_lightweight(monkeypatch) -> None:
    instance = SimpleNamespace(id=uuid4())
    design = SimpleNamespace(id=uuid4(), interior_instances=[instance])
    session = _FakeMutationSession()
    refresh_called = False

    async def fake_interior_ready(_session) -> bool:
        return True

    async def fake_load_design(_session, _design_uuid):
        return design

    async def fake_refresh(*_args, **_kwargs):
        nonlocal refresh_called
        refresh_called = True

    monkeypatch.setattr(subcat_router, "interior_instance_tables_ready", fake_interior_ready)
    monkeypatch.setattr(subcat_router, "_load_design", fake_load_design)
    monkeypatch.setattr(subcat_router, "_refresh_design_interior_instance", fake_refresh)

    response = asyncio.run(
        subcat_router.delete_sub_category_design_interior_instance(
            design.id,
            instance.id,
            session,
        )
    )

    assert response.status_code == 204
    assert session.deleted == [instance]
    assert session.flush_count == 1
    assert session.commit_count == 1
    assert refresh_called is False


def test_order_design_add_refreshes_incrementally_and_keeps_defaults(monkeypatch) -> None:
    item = SimpleNamespace(
        id=uuid4(),
        order_id=uuid4(),
        sub_category_design_id=uuid4(),
        interior_instances=[],
        order_attr_values={},
        order_attr_meta={},
        part_snapshots=[],
        viewer_boxes=[],
    )
    group = SimpleNamespace(id=uuid4(), code="grp")
    order = SimpleNamespace(id=item.order_id, admin_id=uuid4())
    source_design = SimpleNamespace(id=item.sub_category_design_id)
    session = _FakeMutationSession()
    refresh_calls = 0
    aggregate_calls = 0
    state_refresh_calls = 0

    async def fake_interior_ready(_session) -> bool:
        return True

    async def fake_require_item(_session, _item_id):
        for added in session.added:
            if added not in item.interior_instances:
                item.interior_instances.append(added)
        return item

    async def fake_require_order(_session, *, order_id):
        assert order_id == item.order_id
        return order

    async def fake_require_group(_session, *, admin_id, group_id):
        assert admin_id == order.admin_id
        assert group_id == payload.internal_part_group_id
        return group

    async def fake_require_source_design(_session, *, admin_id, design_id):
        assert admin_id == order.admin_id
        assert design_id == item.sub_category_design_id
        return source_design

    async def fake_refresh(_session, *, item, order, source_design, instance, internal_group=None):
        nonlocal refresh_calls
        refresh_calls += 1
        assert internal_group is group
        instance.param_values = {"depth": "550", "width": "900"}
        instance.param_meta = {"depth": {"label": "عمق"}}
        instance.part_snapshots = [{"part_code": "inner-A"}]
        instance.viewer_boxes = [{"width": 10}]

    def fake_refresh_aggregates(*, item, source_design):
        nonlocal aggregate_calls
        aggregate_calls += 1

    def fake_refresh_snapshot_state(*, item, source_design):
        nonlocal state_refresh_calls
        state_refresh_calls += 1

    def fake_serialize_instance(instance):
        return {
            "id": str(instance.id),
            "instance_code": str(instance.instance_code),
            "param_values": dict(instance.param_values),
        }

    monkeypatch.setattr(order_router, "interior_instance_tables_ready", fake_interior_ready)
    monkeypatch.setattr(order_router, "_require_item", fake_require_item)
    monkeypatch.setattr(order_router, "require_accessible_order", fake_require_order)
    monkeypatch.setattr(order_router, "require_accessible_internal_part_group", fake_require_group)
    monkeypatch.setattr(order_router, "require_accessible_sub_category_design", fake_require_source_design)
    monkeypatch.setattr(order_router, "refresh_order_design_interior_instance", fake_refresh)
    monkeypatch.setattr(order_router, "refresh_order_design_aggregate_snapshots", fake_refresh_aggregates)
    monkeypatch.setattr(order_router, "refresh_order_design_snapshot_state", fake_refresh_snapshot_state)
    monkeypatch.setattr(order_router, "_serialize_interior_instance_item", fake_serialize_instance)

    payload = order_router.OrderDesignInteriorInstanceCreate(
        internal_part_group_id=uuid4(),
        placement_z=12,
        param_values={"depth": 550},
    )
    result = asyncio.run(
        order_router.create_order_design_interior_instance(
            item.id,
            payload,
            session,
        )
    )

    assert refresh_calls == 1
    assert aggregate_calls == 1
    assert state_refresh_calls == 1
    assert result["instance_code"] == "grp-01"
    assert result["param_values"] == {"depth": "550", "width": "900"}
    assert session.flush_count == 1
    assert session.commit_count == 1
    assert session.added[0].source_instance_id is None


def test_order_design_delete_rebuilds_full_snapshot(monkeypatch) -> None:
    target = SimpleNamespace(id=uuid4())
    item = SimpleNamespace(id=uuid4(), order_id=uuid4(), sub_category_design_id=uuid4(), interior_instances=[target])
    session = _FakeMutationSession()
    aggregate_calls = 0
    state_refresh_calls = 0

    async def fake_interior_ready(_session) -> bool:
        return True

    async def fake_require_item(_session, _item_id):
        return item

    async def fake_require_order(_session, *, order_id):
        return SimpleNamespace(id=order_id, admin_id=uuid4())

    async def fake_require_source_design(_session, *, admin_id, design_id):
        return SimpleNamespace(id=design_id)

    def fake_refresh_aggregates(*, item, source_design):
        nonlocal aggregate_calls
        aggregate_calls += 1

    def fake_refresh_snapshot_state(*, item, source_design):
        nonlocal state_refresh_calls
        state_refresh_calls += 1

    monkeypatch.setattr(order_router, "interior_instance_tables_ready", fake_interior_ready)
    monkeypatch.setattr(order_router, "_require_item", fake_require_item)
    monkeypatch.setattr(order_router, "require_accessible_order", fake_require_order)
    monkeypatch.setattr(order_router, "require_accessible_sub_category_design", fake_require_source_design)
    monkeypatch.setattr(order_router, "refresh_order_design_aggregate_snapshots", fake_refresh_aggregates)
    monkeypatch.setattr(order_router, "refresh_order_design_snapshot_state", fake_refresh_snapshot_state)

    result = asyncio.run(
        order_router.delete_order_design_interior_instance(
            item.id,
            target.id,
            session,
        )
    )

    assert result.status_code == 204
    assert aggregate_calls == 1
    assert state_refresh_calls == 1
    assert session.deleted == [target]
    assert session.flush_count == 1
    assert session.commit_count == 1


def test_order_design_read_path_can_trigger_snapshot_sync(monkeypatch) -> None:
    item = SimpleNamespace(
        id=uuid4(),
        order_id=uuid4(),
        sub_category_design_id=uuid4(),
        interior_instances=[SimpleNamespace(id=uuid4())],
    )
    session = _FakeScalarSession(item)
    sync_calls = 0

    async def fake_interior_ready(_session) -> bool:
        return True

    async def fake_require_order(_session, *, order_id):
        assert order_id == item.order_id
        return SimpleNamespace(id=order_id, admin_id=uuid4())

    async def fake_require_source_design(_session, *, admin_id, design_id):
        assert design_id == item.sub_category_design_id
        return SimpleNamespace(id=design_id, admin_id=admin_id)

    async def fake_sync(_session, *, item, order, source_design):
        nonlocal sync_calls
        sync_calls += 1
        return True

    monkeypatch.setattr(order_router, "interior_instance_tables_ready", fake_interior_ready)
    monkeypatch.setattr(order_router, "require_accessible_order", fake_require_order)
    monkeypatch.setattr(order_router, "require_accessible_sub_category_design", fake_require_source_design)
    monkeypatch.setattr(order_router, "sync_order_design_snapshot", fake_sync)

    loaded = asyncio.run(order_router._require_item_any_status(session, item.id))

    assert loaded is item
    assert sync_calls == 1
    assert session.commit_count == 1
    assert session.scalar_calls >= 2
