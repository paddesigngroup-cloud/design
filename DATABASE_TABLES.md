# Database Tables

This document records the current database table names and the purpose of each table.
Field definitions, constraints, and relationships will be added later.

## 1. `super_admins`

Purpose:
Stores the internal super-admin accounts owned by our software company.
These accounts are used to control, manage, and monitor the software versions and commercial editions that we sell.

Current business role:
- Represents our own top-level management users, not end customers.
- Will be used for version control access, product release control, and internal administrative permissions.

## 2. `admins`

Purpose:
Stores the customer admin accounts for people or businesses that purchase our software.

Current business role:
- Represents the main administrative account on the customer side.
- Will act as the central ownership and relationship point for many of the future business tables.
- Future table relationships should be designed with this table in mind as a primary parent or reference point where appropriate.
- Has a direct parent-child relationship with the `users` table.

## 3. `users`

Purpose:
Stores the end-user accounts belonging to customers who purchased and use our software.

Current business role:
- Represents the regular users operating under a customer account.
- Sits below the `admins` table in the access hierarchy.
- Will be used for user-level access, ownership, activity tracking, and future operational relationships inside the customer workspace.

Current minimum relationship:
- Each `user` belongs to one `admin`.
- One `admin` can have many `users`.

## 4. `orders`

Purpose:
Stores the orders registered in the software and identifies which customer admin and which user created each order.

Current business role:
- Records the main order registration data.
- Keeps the order number for tracking each order.
- Connects every order to one `admin` and one `user`.
- Stores the order registration time.

Current minimum relationship:
- Each `order` belongs to one `admin`.
- Each `order` belongs to one `user`.
- One `admin` can have many `orders`.
- One `user` can have many `orders`.

## 5. `part_kinds`

Purpose:
Stores the catalog of part categories used in the software, such as unit, shelf, drawer, door, and similar structural or visible cabinet parts.

Current business role:
- Acts as a reusable lookup table for part classification.
- Supports both system-defined part kinds and future admin-specific custom part kinds.
- Replaces the raw spreadsheet-style naming with a cleaner database structure.

Chosen structure logic:
- Business-required fields are preserved with your naming:
  - `admin_id`
  - `part_kind_id`
  - `part_kind_code`
  - `org_part_kind_title`
- `admin_id` means the owner `admin` account that controls this data from the software base.
- This admin can manage and customize the software structure, and those changes will apply to all users under that admin.
- `admin_id = NULL` means the part kind is a global system record.
- `admin_id != NULL` means the part kind belongs to a specific admin and is controlled from that admin level.
- The earlier wrong naming was corrected to `admin_id` so the schema stays consistent with the rest of the system.

Current seeded system records:
- `unit`
- `stretcher`
- `shelf`
- `drawer`
- `partition`
- `door`
- `face_panel`
- `toe_kick`
- `frame`

## 6. `param_groups`

Purpose:
Stores the parameter-group definitions used to organize parameter sections in the software UI, such as attributes, thicknesses, floor properties, door properties, and similar grouped settings.

Current business role:
- Lets each `admin` define and control their own parameter-group structure.
- Supports both system-defined groups and future admin-specific custom groups.
- Controls how grouped parameter sections are presented and ordered in the UI for all users under that admin.

Chosen structure logic:
- The old spreadsheet columns were normalized into the project naming pattern.
- Business fields chosen for this table:
  - `admin_id`
  - `param_group_id`
  - `param_group_code`
  - `org_param_group_title`
  - `param_group_icon_path`
  - `ui_order`
- Internal compatibility fields kept in line with other catalog tables:
  - `code`
  - `title`
  - `sort_order`
  - `is_system`
- `admin_id = NULL` means a global system group.
- `admin_id != NULL` means the group belongs to a specific admin and can override the software structure for all users under that admin.

Mapping from the old spreadsheet:
- `param_group_ux` -> `ui_order`
- `param_group_name` -> `param_group_code`
- `param_group_webp` -> `param_group_icon_path`
- `param_group_info` -> `org_param_group_title`

Current seeded system records:
- `attributes`
- `thicknesses`
- `floor_properties`
- `roof_properties`
- `left_side_properties`
- `right_side_properties`
- `door_properties`
- `back_properties`
- `panel_properties`
- `gap_properties`
- `counter_properties`
- `stretcher_properties`
- `toe_kick_properties`

## Notes

- This document is intentionally limited to table names and table responsibilities.
- Column definitions will be added after the table parameters are finalized.
