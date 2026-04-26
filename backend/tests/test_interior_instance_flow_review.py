from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

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


def test_replace_instance_helpers_preload_design_before_relationship_access(monkeypatch) -> None:
    class _LazyDesignStub:
        def __init__(self) -> None:
            self.id = uuid4()

        @property
        def interior_instances(self):
            raise AssertionError("lazy interior_instances should not be touched before _load_design")

        @property
        def door_instances(self):
            raise AssertionError("lazy door_instances should not be touched before _load_design")

        @property
        def subtractor_instances(self):
            raise AssertionError("lazy subtractor_instances should not be touched before _load_design")

    session = _FakeMutationSession()
    design = _LazyDesignStub()
    load_calls: list[tuple[bool | None, bool | None, bool | None]] = []
    loaded = SimpleNamespace(
        id=design.id,
        interior_instances=[],
        door_instances=[],
        subtractor_instances=[],
    )

    async def fake_load_design(_session, _design_id, *, include_interior=None, include_subtractors=None, include_doors=None):
        load_calls.append((include_interior, include_subtractors, include_doors))
        return loaded

    monkeypatch.setattr(subcat_router, "_load_design", fake_load_design)

    asyncio.run(
        subcat_router._replace_interior_instances(
            session,
            design=design,
            payloads=[],
            include_interior=True,
            include_subtractors=False,
            include_doors=False,
        )
    )
    asyncio.run(
        subcat_router._replace_door_instances(
            session,
            design=design,
            payloads=[],
            include_interior=False,
            include_subtractors=False,
            include_doors=True,
        )
    )
    asyncio.run(
        subcat_router._replace_subtractor_instances(
            session,
            design=design,
            payloads=[],
            include_interior=False,
            include_subtractors=True,
            include_doors=False,
        )
    )

    assert load_calls == [
        (True, False, False),
        (True, False, False),
        (False, False, True),
        (False, False, True),
        (False, True, False),
        (False, True, False),
    ]


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

    async def fake_door_ready(_session) -> bool:
        return False

    async def fake_subtractor_ready(_session) -> bool:
        return False

    async def fake_next_state(_session, **_kwargs):
        return "inner-01", 0, {"width": 10}, {"depth": "550"}, {"depth": {"label": "عمق"}}

    async def fake_load_design(_session, _design_uuid):
        for item in session.added:
            if item not in design.interior_instances:
                design.interior_instances.append(item)
        return design

    async def fake_require_group(_session, *, admin_id, group_id):
        assert admin_id == design.admin_id
        assert group_id == payload.internal_part_group_id
        return SimpleNamespace(id=group_id, line_color="#8A98A3")

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
    monkeypatch.setattr(subcat_router, "require_accessible_internal_part_group", fake_require_group)
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


def test_subcategory_duplicate_refreshes_only_clone_and_keeps_source_values(monkeypatch) -> None:
    source_instance = SimpleNamespace(
        id=uuid4(),
        internal_part_group_id=uuid4(),
        instance_code="inner-01",
        ui_order=1,
        placement_z=24.5,
        line_color="#112233",
        param_values={"depth": "550"},
        status="draft",
    )
    design = SimpleNamespace(
        id=uuid4(),
        admin_id=uuid4(),
        sub_category_id=uuid4(),
        interior_instances=[source_instance],
    )
    session = _FakeMutationSession()
    refresh_calls: list[str] = []

    async def fake_interior_ready(_session) -> bool:
        return True

    async def fake_load_design(_session, _design_uuid):
        for item in session.added:
            if item not in design.interior_instances:
                design.interior_instances.append(item)
        return design

    async def fake_require_group(_session, *, admin_id, group_id):
        assert admin_id == design.admin_id
        assert group_id == source_instance.internal_part_group_id
        return SimpleNamespace(id=group_id, code="inner", line_color="#445566")

    async def fake_next_state(_session, **kwargs):
        assert kwargs["group_id"] == source_instance.internal_part_group_id
        assert kwargs["placement_z"] == source_instance.placement_z
        assert kwargs["ui_order"] == 2
        assert kwargs["param_values"] == source_instance.param_values
        return "inner-03", 2, {"width": 99}, {"depth": "550"}, {"depth": {"label": "عمق"}}

    async def fake_refresh(_session, *, design, instance):
        refresh_calls.append(str(instance.id))
        instance.part_snapshots = [{"part_code": "clone"}]
        instance.viewer_boxes = [{"width": 99}]
        instance.status = "draft"

    class _FakeInteriorInstance:
        def __init__(self, **kwargs) -> None:
            for key, value in kwargs.items():
                setattr(self, key, value)
            self.id = None
            self.part_snapshots = []
            self.viewer_boxes = []
            self.status = kwargs.get("status", "draft")

    monkeypatch.setattr(subcat_router, "interior_instance_tables_ready", fake_interior_ready)
    monkeypatch.setattr(subcat_router, "_load_design", fake_load_design)
    monkeypatch.setattr(subcat_router, "require_accessible_internal_part_group", fake_require_group)
    monkeypatch.setattr(subcat_router, "_next_interior_instance_state", fake_next_state)
    monkeypatch.setattr(subcat_router, "_refresh_design_interior_instance", fake_refresh)
    monkeypatch.setattr(subcat_router, "SubCategoryDesignInteriorInstance", _FakeInteriorInstance)

    duplicated = asyncio.run(
        subcat_router.duplicate_sub_category_design_interior_instance(
            design.id,
            source_instance.id,
            session,
        )
    )

    assert duplicated.instance_code == "inner-03"
    assert duplicated.ui_order == 2
    assert duplicated.line_color == "#112233"
    assert duplicated.param_values == {"depth": "550"}
    assert len(refresh_calls) == 1
    assert refresh_calls[0] == str(session.added[0].id)
    assert session.commit_count == 1


def test_subcategory_duplicate_returns_404_for_unknown_instance(monkeypatch) -> None:
    design = SimpleNamespace(id=uuid4(), interior_instances=[])
    session = _FakeMutationSession()

    async def fake_interior_ready(_session) -> bool:
        return True

    async def fake_load_design(_session, _design_uuid):
        return design

    monkeypatch.setattr(subcat_router, "interior_instance_tables_ready", fake_interior_ready)
    monkeypatch.setattr(subcat_router, "_load_design", fake_load_design)

    with pytest.raises(subcat_router.HTTPException) as exc_info:
        asyncio.run(
            subcat_router.duplicate_sub_category_design_interior_instance(
                design.id,
                uuid4(),
                session,
            )
        )

    assert exc_info.value.status_code == 404


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


def test_order_design_add_uses_created_instance_when_reloaded_collection_is_empty(monkeypatch) -> None:
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
    refreshed_instances: list[object] = []

    async def fake_interior_ready(_session) -> bool:
        return True

    async def fake_require_item(_session, _item_id):
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
        refreshed_instances.append(instance)
        instance.param_values = {"depth": "550"}
        instance.part_snapshots = [{"part_code": "inner-A"}]
        instance.viewer_boxes = [{"width": 10}]

    def fake_refresh_aggregates(*, item, source_design):
        assert len(item.interior_instances) == 1

    def fake_refresh_snapshot_state(*, item, source_design):
        assert len(item.interior_instances) == 1

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

    assert len(refreshed_instances) == 1
    assert refreshed_instances[0] is session.added[0]
    assert len(item.interior_instances) == 1
    assert result["instance_code"] == "grp-01"
    assert session.commit_count == 1


def test_order_design_duplicate_recomputes_clone_and_aggregate_state(monkeypatch) -> None:
    source = SimpleNamespace(
        id=uuid4(),
        source_instance_id=uuid4(),
        internal_part_group_id=uuid4(),
        instance_code="grp-01",
        ui_order=1,
        placement_z=12.0,
        line_color="#223344",
        param_values={"depth": "550"},
        status="draft",
    )
    item = SimpleNamespace(
        id=uuid4(),
        order_id=uuid4(),
        sub_category_design_id=uuid4(),
        interior_instances=[source],
        order_attr_values={},
        order_attr_meta={},
        part_snapshots=[],
        viewer_boxes=[],
    )
    group = SimpleNamespace(id=source.internal_part_group_id, code="grp", line_color="#556677")
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
        assert group_id == source.internal_part_group_id
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
        instance.part_snapshots = [{"part_code": "clone"}]
        instance.viewer_boxes = [{"width": 88}]

    def fake_refresh_aggregates(*, item, source_design):
        nonlocal aggregate_calls
        aggregate_calls += 1
        assert item.interior_instances[-1] is session.added[0]
        assert session.added[0].part_snapshots == [{"part_code": "clone"}]
        assert session.added[0].viewer_boxes == [{"width": 88}]

    def fake_refresh_snapshot_state(*, item, source_design):
        nonlocal state_refresh_calls
        state_refresh_calls += 1

    def fake_serialize_instance(instance):
        return {
            "id": str(instance.id),
            "instance_code": str(instance.instance_code),
            "ui_order": int(instance.ui_order),
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

    result = asyncio.run(
        order_router.duplicate_order_design_interior_instance(
            item.id,
            source.id,
            session,
        )
    )

    assert refresh_calls == 1
    assert aggregate_calls == 1
    assert state_refresh_calls == 1
    assert result["instance_code"] == "grp-03"
    assert result["ui_order"] == 2
    assert result["param_values"] == {"depth": "550", "width": "900"}
    assert session.added[0].source_instance_id == source.source_instance_id
    assert session.added[0].line_color == "#223344"
    assert session.commit_count == 1


def test_order_design_duplicate_returns_404_for_unknown_instance(monkeypatch) -> None:
    item = SimpleNamespace(
        id=uuid4(),
        order_id=uuid4(),
        sub_category_design_id=uuid4(),
        interior_instances=[],
    )
    session = _FakeMutationSession()

    async def fake_interior_ready(_session) -> bool:
        return True

    async def fake_require_item(_session, _item_id):
        return item

    monkeypatch.setattr(order_router, "interior_instance_tables_ready", fake_interior_ready)
    monkeypatch.setattr(order_router, "_require_item", fake_require_item)

    with pytest.raises(order_router.HTTPException) as exc_info:
        asyncio.run(
            order_router.duplicate_order_design_interior_instance(
                item.id,
                uuid4(),
                session,
            )
        )

    assert exc_info.value.status_code == 404


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

    async def fake_door_ready(_session) -> bool:
        return False

    async def fake_subtractor_ready(_session) -> bool:
        return False

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
    monkeypatch.setattr(order_router, "door_instance_tables_ready", fake_door_ready)
    monkeypatch.setattr(order_router, "subtractor_instance_tables_ready", fake_subtractor_ready)
    monkeypatch.setattr(order_router, "require_accessible_order", fake_require_order)
    monkeypatch.setattr(order_router, "require_accessible_sub_category_design", fake_require_source_design)
    monkeypatch.setattr(order_router, "sync_order_design_snapshot", fake_sync)

    loaded = asyncio.run(order_router._require_item_any_status(session, item.id))

    assert loaded is item
    assert sync_calls == 1
    assert session.commit_count == 1
    assert session.scalar_calls >= 2


def test_order_patch_interior_include_design_returns_bundle(monkeypatch) -> None:
    instance_id = uuid4()
    item = SimpleNamespace(
        id=uuid4(),
        order_id=uuid4(),
        sub_category_design_id=uuid4(),
        interior_instances=[
            SimpleNamespace(
                id=instance_id,
                internal_part_group_id=uuid4(),
                instance_code="inner-01",
                line_color="#8A98A3",
                ui_order=0,
                placement_z=0.0,
                interior_box_snapshot={},
                param_values={},
                param_meta={},
                part_snapshots=[],
                viewer_boxes=[],
                status="draft",
            )
        ],
    )

    async def _ready(_session):
        return True

    async def _require_item(_session, _item_id):
        return item

    async def _require_order(_session, *, order_id):
        return SimpleNamespace(id=order_id, admin_id=uuid4())

    async def _require_design(_session, *, admin_id, design_id):
        return SimpleNamespace(id=design_id)

    async def _refresh(*_args, **_kwargs):
        return None

    def _refresh_aggregate(**_kwargs):
        return None

    def _refresh_state(**_kwargs):
        return None

    async def _commit(*_args, **_kwargs):
        return None

    async def _sync(*_args, **_kwargs):
        return True

    async def _design_bundle(*_args, **_kwargs):
        return order_router.OrderDesignItem(
            id=item.id,
            order_id=item.order_id,
            admin_id=uuid4(),
            user_id=uuid4(),
            sub_category_design_id=item.sub_category_design_id,
            sub_category_id=uuid4(),
            design_outline_color="#7A4A2B",
            design_code="z1",
            design_title="demo",
            manual_name=None,
            instance_code="U1",
            sort_order=1,
            status="draft",
            order_attr_values={},
            order_attr_meta={},
            part_snapshots=[],
            viewer_boxes=[{"width": 10}],
            boolean_targets=[],
            boolean_cutters=[],
            boolean_result=[],
            interior_instances=[],
            subtractor_instances=[],
            door_instances=[],
            snapshot_checksum="s1",
        )

    monkeypatch.setattr(order_router, "interior_instance_tables_ready", _ready)
    monkeypatch.setattr(order_router, "_require_item", _require_item)
    monkeypatch.setattr(order_router, "require_accessible_order", _require_order)
    monkeypatch.setattr(order_router, "require_accessible_sub_category_design", _require_design)
    monkeypatch.setattr(order_router, "refresh_order_design_interior_instance", _refresh)
    monkeypatch.setattr(order_router, "refresh_order_design_aggregate_snapshots", _refresh_aggregate)
    monkeypatch.setattr(order_router, "refresh_order_design_snapshot_state", _refresh_state)
    monkeypatch.setattr(order_router, "sync_order_design_snapshot", _sync)
    monkeypatch.setattr(order_router, "_commit_order_design_changes", _commit)
    monkeypatch.setattr(order_router, "_serialize_design_item_for_patch_response", _design_bundle)

    payload = order_router.OrderDesignInteriorInstanceUpdate(
        placement_z=5,
        ui_order=1,
        instance_code="inner-02",
        line_color="#8A98A3",
        param_values={"w": "10"},
    )
    response = asyncio.run(
        order_router.update_order_design_interior_instance(
            item.id,
            instance_id,
            payload,
            include_design=True,
            session=SimpleNamespace(),
        )
    )

    assert str(response.id) == str(instance_id)
    assert response.design is not None
    assert str(response.design.id) == str(item.id)


def test_order_patch_subtractor_include_design_returns_bundle(monkeypatch) -> None:
    instance_id = uuid4()
    item = SimpleNamespace(
        id=uuid4(),
        order_id=uuid4(),
        sub_category_design_id=uuid4(),
        subtractor_instances=[
            SimpleNamespace(
                id=instance_id,
                subtractor_part_group_id=uuid4(),
                instance_code="sub-01",
                line_color="#8A98A3",
                ui_order=0,
                placement_z=0.0,
                param_values={},
                param_meta={},
                part_snapshots=[],
                viewer_boxes=[],
                status="draft",
            )
        ],
    )

    async def _ready(_session):
        return True

    async def _require_item(_session, _item_id):
        return item

    async def _require_order(_session, *, order_id):
        return SimpleNamespace(id=order_id, admin_id=uuid4())

    async def _require_design(_session, *, admin_id, design_id):
        return SimpleNamespace(id=design_id)

    async def _sync(*_args, **_kwargs):
        return True

    async def _commit(*_args, **_kwargs):
        return None

    async def _sync(*_args, **_kwargs):
        return True

    async def _design_bundle(*_args, **_kwargs):
        return order_router.OrderDesignItem(
            id=item.id,
            order_id=item.order_id,
            admin_id=uuid4(),
            user_id=uuid4(),
            sub_category_design_id=item.sub_category_design_id,
            sub_category_id=uuid4(),
            design_outline_color="#7A4A2B",
            design_code="z1",
            design_title="demo",
            manual_name=None,
            instance_code="U1",
            sort_order=1,
            status="draft",
            order_attr_values={},
            order_attr_meta={},
            part_snapshots=[],
            viewer_boxes=[{"width": 10}],
            boolean_targets=[],
            boolean_cutters=[],
            boolean_result=[],
            interior_instances=[],
            subtractor_instances=[],
            door_instances=[],
            snapshot_checksum="s1",
        )

    monkeypatch.setattr(order_router, "subtractor_instance_tables_ready", _ready)
    monkeypatch.setattr(order_router, "_require_item", _require_item)
    monkeypatch.setattr(order_router, "require_accessible_order", _require_order)
    monkeypatch.setattr(order_router, "require_accessible_sub_category_design", _require_design)
    monkeypatch.setattr(order_router, "sync_order_design_snapshot", _sync)
    monkeypatch.setattr(order_router, "_commit_order_design_changes", _commit)
    monkeypatch.setattr(order_router, "_serialize_design_item_for_patch_response", _design_bundle)

    payload = order_router.OrderDesignSubtractorInstanceUpdate(
        placement_z=5,
        ui_order=1,
        instance_code="sub-02",
        line_color="#8A98A3",
        param_values={"w": "10"},
    )
    response = asyncio.run(
        order_router.update_order_design_subtractor_instance(
            item.id,
            instance_id,
            payload,
            include_design=True,
            session=SimpleNamespace(),
        )
    )

    assert str(response.id) == str(instance_id)
    assert response.design is not None
    assert str(response.design.id) == str(item.id)


def test_order_patch_door_include_design_returns_bundle(monkeypatch) -> None:
    instance_id = uuid4()
    item = SimpleNamespace(
        id=uuid4(),
        order_id=uuid4(),
        sub_category_design_id=uuid4(),
        door_instances=[
            SimpleNamespace(
                id=instance_id,
                door_part_group_id=uuid4(),
                instance_code="door-01",
                line_color="#8A98A3",
                ui_order=0,
                structural_part_formula_ids=[],
                dependent_interior_instance_ids=[],
                controller_box_snapshot={},
                param_values={},
                param_meta={},
                part_snapshots=[],
                viewer_boxes=[],
                status="draft",
            )
        ],
    )

    async def _ready(_session):
        return True

    async def _require_item(_session, _item_id):
        return item

    async def _require_order(_session, *, order_id):
        return SimpleNamespace(id=order_id, admin_id=uuid4())

    async def _require_design(_session, *, admin_id, design_id):
        return SimpleNamespace(id=design_id)

    async def _require_group(*_args, **_kwargs):
        return SimpleNamespace(controller_type="", controller_bindings={})

    async def _refresh(*_args, **_kwargs):
        return None

    def _refresh_aggregate(**_kwargs):
        return None

    def _refresh_state(**_kwargs):
        return None

    async def _commit(*_args, **_kwargs):
        return None

    async def _sync(*_args, **_kwargs):
        return True

    async def _design_bundle(*_args, **_kwargs):
        return order_router.OrderDesignItem(
            id=item.id,
            order_id=item.order_id,
            admin_id=uuid4(),
            user_id=uuid4(),
            sub_category_design_id=item.sub_category_design_id,
            sub_category_id=uuid4(),
            design_outline_color="#7A4A2B",
            design_code="z1",
            design_title="demo",
            manual_name=None,
            instance_code="U1",
            sort_order=1,
            status="draft",
            order_attr_values={},
            order_attr_meta={},
            part_snapshots=[],
            viewer_boxes=[{"width": 10}],
            boolean_targets=[],
            boolean_cutters=[],
            boolean_result=[],
            interior_instances=[],
            subtractor_instances=[],
            door_instances=[],
            snapshot_checksum="s1",
        )

    monkeypatch.setattr(order_router, "door_instance_tables_ready", _ready)
    monkeypatch.setattr(order_router, "_require_item", _require_item)
    monkeypatch.setattr(order_router, "require_accessible_order", _require_order)
    monkeypatch.setattr(order_router, "require_accessible_sub_category_design", _require_design)
    monkeypatch.setattr(order_router, "require_accessible_door_part_group", _require_group)
    monkeypatch.setattr(order_router, "refresh_order_design_door_instance", _refresh)
    monkeypatch.setattr(order_router, "refresh_order_design_aggregate_snapshots", _refresh_aggregate)
    monkeypatch.setattr(order_router, "refresh_order_design_snapshot_state", _refresh_state)
    monkeypatch.setattr(order_router, "sync_order_design_snapshot", _sync)
    monkeypatch.setattr(order_router, "_commit_order_design_changes", _commit)
    monkeypatch.setattr(order_router, "_serialize_design_item_for_patch_response", _design_bundle)

    payload = order_router.OrderDesignDoorInstanceUpdate(
        ui_order=1,
        instance_code="door-02",
        line_color="#8A98A3",
        structural_part_formula_ids=[],
        dependent_interior_instance_ids=[],
        param_values={"w": "10"},
    )
    response = asyncio.run(
        order_router.update_order_design_door_instance(
            item.id,
            instance_id,
            payload,
            include_design=True,
            session=SimpleNamespace(),
        )
    )

    assert str(response.id) == str(instance_id)
    assert response.design is not None
    assert str(response.design.id) == str(item.id)
