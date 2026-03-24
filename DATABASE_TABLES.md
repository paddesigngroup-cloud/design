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
- Records the main order registration data before wall/design detail is attached.
- Keeps both an order name and an order number for tracking each order.
- Connects every order to one `admin` and one `user`.
- Stores the order registration time.
- Stores the current workflow state of the order.
- Holds short order-level notes for UX and sales follow-up.

Chosen v1 structure logic:
- Business fields for this phase:
  - `order_name`
  - `order_number`
  - `status`
  - `notes`
  - `submitted_at`
  - `admin_id`
  - `user_id`
- `order_name` is the human-facing design/job name that the UI uses before any walls or drawings exist.
- `order_number` is the system tracking code and is generated automatically.
- `status` is currently one of:
  - `draft`
  - `designing`
  - `submitted`
  - `archived`
- `notes` stores short free-text context for the order header and future workflow.
- In this phase, `orders` is intentionally only the UX parent record.
- Future tables for walls, design snapshots, and other formal links should reference `order_id` separately rather than being merged into this table.

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
- `shelve`
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

## 7. `params`

Purpose:
Stores the actual parameter definitions used by each part kind, such as width, depth, height, thickness values, roof/floor/side settings, stretcher settings, door settings, panel settings, and counter settings.

Current business role:
- Lets each `admin` define and control their own parameter list per part kind.
- Connects each parameter to a real `part_kind` and a real `param_group`.
- Controls the parameter title, code, group placement, and UI display order.
- Supports both system-defined parameters and future admin-specific custom parameters.

Chosen structure logic:
- Spreadsheet-style naming was normalized into the project naming pattern.
- Business fields chosen for this table:
  - `admin_id`
  - `param_id`
  - `part_kind_id`
  - `param_code`
  - `param_title_en`
  - `param_title_fa`
  - `param_group_id`
  - `ui_order`
- Internal compatibility fields kept in line with other catalog tables:
  - `code`
  - `title`
  - `sort_order`
  - `is_system`
- `admin_id = NULL` means a global system parameter.
- `admin_id != NULL` means the parameter belongs to a specific admin and can override the software structure for all users under that admin.
- `part_kind_id` links the parameter to a row in `part_kinds`.
- `param_group_id` links the parameter to a row in `param_groups`.

Mapping from the old spreadsheet:
- `admin_user_id` -> `admin_id`
- `id` -> `param_id`
- `param` -> `param_code`
- `param_group_ux` -> mapped to real `param_group_id`
- `param_turn_ux` -> `ui_order`

Current seeded system records:
- Base `unit` parameters such as `width`, `depth`, `height`, `unit_floor_offset`
- Thickness parameters such as `unit_thickness`, `back_thickness`, `door_thickness`, `frame_thickness`, `panel_thickness`, `counter_thickness`
- Floor, roof, left-side, right-side, back, panel, gap, counter, and stretcher parameter sets
- Door-specific parameter set

## 8. `base_formulas`

Purpose:
Stores the base formula definitions used by the software engine to calculate construction logic from the parameter set, with each formula represented as an expression string and a stable formula code.

Current business role:
- Lets each `admin` own and manage the formula set that drives calculations for all users under that admin.
- Supports both system-defined formulas and future admin-specific formula overrides.
- Acts as the next layer after `params`, because formula expressions are written based on the parameter codes already defined in the system.
- Keeps the database structure consistent with the ownership model already used in `part_kinds`, `param_groups`, and `params`.

Chosen structure logic:
- The spreadsheet-style formula list should be normalized into the same naming pattern as the other catalog tables.
- Business fields chosen for this table:
  - `admin_id`
  - `fo_id`
  - `param_formula`
  - `formula`
- Recommended internal compatibility fields, kept aligned with the other software-structure tables:
  - `code`
  - `title`
  - `sort_order`
  - `is_system`
- `admin_id` means the owner `admin` account whose software structure uses this base formula set.
- `admin_id = NULL` means the formula is a global system formula.
- `admin_id != NULL` means the formula belongs to a specific admin and can override the software formula structure for all users under that admin.
- `param_formula` should remain the stable formula code such as `f1`, `f2`, `f3`.
- `formula` stores the real executable expression string.

Relationship decision:
- Even if the old Excel file contains `super_admin_id`, this table should not be modeled under `super_admins`.
- This table must be owned by `admins`, because the formula set is described as being created per admin from that admin's parameter structure.
- Therefore the correct relationship field for the database schema is `admin_id`, not `super_admin_id`.

Mapping from the old spreadsheet:
- `super_admin_id` -> `admin_id`
- `fo_id` -> `fo_id`
- `param_formula` -> `param_formula`
- `formula` -> `formula`

Current seeded system records:
- Formula codes such as `f1` through the current seeded formula range from the spreadsheet
- Each record stores one base formula expression built from the parameter codes already defined in `params`

## 9. `part_formulas`

Purpose:
Stores the part-generation formulas used by the software to create real cabinet pieces from `params` and `base_formulas`, with each row representing one buildable part definition inside a parent `part_kind`.

Current business role:
- Lets each `admin` define how a cabinet structure turns into actual generated parts such as floor, roof, left side, right side, back, and stretcher variants.
- Supports both system-defined part formulas and future admin-specific overrides.
- Sits after `base_formulas`, because these expressions can use both raw parameter codes and base formula codes such as `f1`, `f2`, and similar helper formulas.
- Stores not only the size formulas of each generated part, but also the center-position formulas needed for placing that part in the engine.

Chosen structure logic:
- This sheet was modeled as a dedicated table rather than being merged into `part_kinds`, because one `part_kind` can generate multiple sub-parts.
- Business fields chosen for this table:
  - `admin_id`
  - `part_formula_id`
  - `part_kind_id`
  - `part_sub_kind_id`
  - `part_code`
  - `part_title`
  - `formula_l`
  - `formula_w`
  - `formula_width`
  - `formula_depth`
  - `formula_height`
  - `formula_cx`
  - `formula_cy`
  - `formula_cz`
- Internal compatibility fields kept aligned with the other software-structure tables:
  - `code`
  - `title`
  - `sort_order`
  - `is_system`
- `admin_id = NULL` means a global system part-formula row.
- `admin_id != NULL` means the row belongs to a specific admin and can override the default generated-part structure for that admin.
- `part_kind_id` links each row to a parent row in `part_kinds`.
- `part_sub_kind_id` is the stable sub-type number inside that `part_kind`.
- Formula columns can use both parameter codes from `params` and base formula codes from `base_formulas`.

Mapping from the old spreadsheet:
- `pi_id` -> `part_formula_id`
- `part_kind_id` -> `part_kind_id`
- `part_sub_kind_id` -> `part_sub_kind_id`
- `part_code` -> `part_code`
- `part_title` -> `part_title`
- `l` -> `formula_l`
- `w` -> `formula_w`
- `width` -> `formula_width`
- `depth` -> `formula_depth`
- `height` -> `formula_height`
- `cx` -> `formula_cx`
- `cy` -> `formula_cy`
- `cz` -> `formula_cz`

Current seeded system records:
- `unit` sub-parts such as `floor`, `roof`, `le_side`, `ri_side`, and `back`
- `stretcher` sub-parts such as top front/back horizontal stretchers and top/bottom back vertical stretchers
- Each seeded row stores full formula expressions for size and placement axes

## 10. `templates`

Purpose:
Stores the high-level furniture template definitions that an `admin` wants to make available in the software, such as cabinet, closet, and similar top-level design families.

Current business role:
- Lets each `admin` decide which main design templates exist in their workspace.
- Acts as the parent catalog for future higher-level structure, so later order/design data can point to a chosen template family before going into detailed parts and formulas.
- Supports both system-defined templates and future admin-specific templates.

Chosen structure logic:
- The provided Excel sample only contains the meaningful columns `temp_id` and `temp_title`.
- The other visible spreadsheet columns were intentionally ignored because they do not carry stable business data for the database schema.
- Business fields chosen for this table:
  - `admin_id`
  - `temp_id`
  - `temp_title`
- Internal compatibility fields kept aligned with the other software-structure tables:
  - `code`
  - `title`
  - `sort_order`
  - `is_system`
- `admin_id = NULL` means a global system template.
- `admin_id != NULL` means the template belongs to one specific `admin` and is available for all users under that admin.
- `temp_id` is the stable numeric template identifier from the spreadsheet.
- `temp_title` stores the user-facing Persian template title such as `کابینت`.
- Because the source sheet has no explicit code column, internal `code` is generated from `temp_id` in the format `template_{temp_id}`.

Relationship decision:
- This table belongs directly to `admins`, not to `users` and not to `super_admins`.
- The user described it as the set of design families that each customer admin wants to define, so `admin_id` is the correct ownership field.

Mapping from the spreadsheet:
- `temp_id` -> `temp_id`
- `temp_title` -> `temp_title`
- ignored columns -> not carried into the database schema

Current seeded system records:
- `1 / کابینت`

## 11. `categories`

Purpose:
Stores the category list that sits under each `template`, such as floor-standing, wall-mounted, or tall-unit groups that an `admin` wants to expose inside that template family.

Current business role:
- Lets each `admin` organize the next level under a selected `template`.
- Creates a direct hierarchy of `template -> category`.
- Supports both system-defined categories and future admin-specific category overrides.

Chosen structure logic:
- The provided Excel sample contains the meaningful columns `temp_id`, `cat_id`, and `cat_title`.
- `admin_user_id` from the sheet is normalized into `admin_id` to stay consistent with the rest of the schema.
- Business fields chosen for this table:
  - `admin_id`
  - `temp_id`
  - `cat_id`
  - `cat_title`
- Internal compatibility fields kept aligned with the other software-structure tables:
  - `code`
  - `title`
  - `sort_order`
  - `is_system`
- `admin_id = NULL` means a global system category.
- `admin_id != NULL` means the category belongs to one specific `admin`.
- `temp_id` links each category to one real row in `templates`.
- Because the source sheet has no explicit code column, internal `code` is generated from `cat_id` in the format `category_{cat_id}`.

Relationship decision:
- This table belongs to `admins` for ownership and to `templates` for hierarchy.
- A category cannot exist without a valid `template`.
- Admin-scoped categories should only point to system templates or templates owned by the same admin.

Mapping from the spreadsheet:
- `admin_user_id` -> `admin_id`
- `temp_id` -> `temp_id`
- `cat_id` -> `cat_id`
- `cat_title` -> `cat_title`

Current seeded system records:
- `1 / 1 / زمینی`
- `1 / 2 / هوایی`
- `1 / 3 / ایستاده`

## 12. `sub_categories`

Purpose:
Stores the sub-category models under each `category`, such as concrete layout variants that an `admin` wants to offer for a selected category.

Current business role:
- Lets each `admin` define how many models exist under each category.
- Creates the next hierarchy level after `categories`.
- Works together with the sub-category default-values table so every sub-category can carry default parameter values.

Chosen structure logic:
- The Excel sample contains fixed columns `temp_id`, `cat_id`, `sub_cat_id`, `sub_cat`, plus many dynamic columns whose names match `params.param_code`.
- Because parameter columns are dynamic and must grow automatically whenever a new parameter is defined, the implementation is internally normalized:
  - `sub_categories`
  - `sub_category_param_defaults`
- In API/UI, this still behaves like one logical editable table.
- Business fields chosen for the master table:
  - `admin_id`
  - `temp_id`
  - `cat_id`
  - `sub_cat_id`
  - `sub_cat_title`
- Internal compatibility fields kept aligned with the other software-structure tables:
  - `code`
  - `title`
  - `sort_order`
  - `is_system`

Relationship decision:
- This table belongs to `admins` for ownership, to `templates` for top-level placement, and to `categories` for direct hierarchy.
- A sub-category cannot exist without a valid `category`.
- The related `sub_category_param_defaults` rows link each sub-category to every matching `param`.

Default-values behavior:
- Every time the software reads or creates sub-category rows, it ensures the matching parameter-default rows exist.
- This means any newly defined `param` can automatically appear in the logical sub-category table without adding real database columns.
- `default_value` is stored per `(sub_category, param)` pair.

Mapping from the spreadsheet:
- `admin_user_id` -> `admin_id`
- `temp_id` -> `temp_id`
- `cat_id` -> `cat_id`
- `sub_cat_id` -> `sub_cat_id`
- `sub_cat` -> `sub_cat_title`
- every remaining parameter-code column -> `sub_category_param_defaults.default_value`

Current seeded system records:
- `temp_id=1 / cat_id=1 / sub_cat_id=1 / کاربردی`

## Notes

- This document is intentionally limited to table names and table responsibilities.
- Column definitions will be added after the table parameters are finalized.
