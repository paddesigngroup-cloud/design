# Review: Interior Instance Add/Remove Cost in `order_designs` vs `sub_category_designs`

## Summary

- The slow path in `order_designs` is not the raw insert/delete itself.
- The main cost comes from rebuilding the full order-design snapshot after each interior-instance mutation.
- `sub_category_designs` uses a lighter flow for interior changes, especially on delete.

## What Happens in `sub_category_designs`

- Add uses `_next_interior_instance_state(...)` to compute the new instance state, then calls `_refresh_design_interior_instance(...)`.
- Update also calls `_refresh_design_interior_instance(...)`.
- Delete only does `delete + flush + commit`.
- Full rebuilds are reserved for whole-design changes such as `rebuild_design_snapshots(...)` and explicit rebuild endpoints.

## What Happens in `order_designs`

- Add, update, and delete all call `_rebuild_order_design_after_interior_change(...)`.
- That method rebuilds the full snapshot through `build_order_design_snapshot(...)`.
- The rebuild re-syncs:
  - `part_snapshots`
  - `viewer_boxes`
  - `order_attr_meta`
  - `snapshot_checksum`
  - every current interior instance payload

## Why `order_designs` Is Heavier

- `order_designs` keeps an order-specific detached snapshot rather than relying on the source sub-category design at read time.
- `source_instance_id` shows the link to source interiors, but the order design still persists its own mutable state.
- `snapshot_checksum` and snapshot-state metadata add freshness tracking and re-sync behavior on top of the interior-instance feature.
- Because of that, the order-design layer intentionally pays extra compute to keep its snapshot self-contained.

## Read-Path Cost

- The heavier behavior is not limited to write operations.
- `_require_item_any_status(...)` can call `sync_order_design_snapshot(...)` when an order design has interior instances.
- That means some reads can also trigger snapshot synchronization work.

## Historical Context

- Both interior-instance tables were introduced together in migration `20260325_0031_add_interior_instances_to_designs.py`.
- The extra snapshot-related cost for order designs was added afterward in `20260326_0032_add_snapshot_checksum_to_order_designs.py` and related snapshot-meta logic.
- So this is primarily a newer snapshot-oriented architecture choice, not a legacy branch that simply survived unchanged.

## Business-Necessary vs Optimization Candidates

### Likely business-necessary

- Keeping `order_designs` independent from source-design drift.
- Persisting order-level attribute overrides and resolved snapshot payloads.
- Freshness tracking with marker/checksum state.

### Likely optimization candidates

- Replace full rebuild after interior add/update/delete with targeted interior refresh when base/order attributes did not change.
- Prevent read-path sync unless marker/checksum state is actually stale.
- Avoid rebuilding root `viewer_boxes` and root `part_snapshots` when only an interior instance changed.
- Use `source_instance_id` more aggressively for incremental refresh flows.

## Evidence Locked by Tests

- `sub_category_designs` add uses instance refresh and delete stays lightweight.
- `order_designs` add/delete route through full rebuild.
- `order_designs` read flow can trigger snapshot sync when interiors exist.
