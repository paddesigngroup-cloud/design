from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

from designkp_backend.api.routers import internal_part_groups as router


class _FakeScalarsResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeSession:
    def __init__(self, defaults):
        self.defaults = defaults
        self.deleted = []
        self.flush_count = 0

    async def scalars(self, stmt):
        text = str(stmt)
        if "FROM internal_part_group_param_defaults" in text:
            return _FakeScalarsResult(self.defaults)
        return _FakeScalarsResult([])

    async def delete(self, row):
        self.deleted.append(row)

    async def flush(self):
        self.flush_count += 1

    def add(self, _item):
        raise AssertionError("No new rows should be added in this test")


def test_sync_group_param_defaults_only_seeds_default_values(monkeypatch) -> None:
    param = SimpleNamespace(param_id=10, param_code="u_th", param_title_fa="ضخامت یونیت", title="Unit Thickness")
    seed_row = SimpleNamespace(
        param_id=10,
        display_title="ضخامت بدنه",
        default_value="18",
        icon_path="seed-icon.webp",
        input_mode="binary",
        binary_off_label="خاموش",
        binary_on_label="روشن",
        binary_off_icon_path="off.webp",
        binary_on_icon_path="on.webp",
        description_text="توضیح نمونه",
    )
    existing_row = SimpleNamespace(
        param_id=10,
        display_title="ضخامت یونیت",
        default_value=None,
        icon_path=None,
        input_mode="value",
        binary_off_label="0",
        binary_on_label="1",
        binary_off_icon_path=None,
        binary_on_icon_path=None,
        description_text=None,
    )
    group = SimpleNamespace(id=uuid4(), admin_id=None)
    group.__dict__["param_groups"] = [SimpleNamespace(param_group_id=1, enabled=True)]

    async def fake_params_for_internal_group(_session, _group):
        return [param]

    async def fake_load_first_sub_category_default_seed(_session, *, admin_id, param_ids):
        assert admin_id is None
        assert param_ids == {10}
        return {10: seed_row}

    monkeypatch.setattr(router, "_params_for_internal_group", fake_params_for_internal_group)
    monkeypatch.setattr(router, "_load_first_sub_category_default_seed", fake_load_first_sub_category_default_seed)

    changed = asyncio.run(router._sync_group_param_defaults(_FakeSession([existing_row]), group))

    assert changed is True
    assert existing_row.default_value == "18"
    assert existing_row.display_title == "ضخامت یونیت"
    assert existing_row.icon_path is None
    assert existing_row.input_mode == "value"
