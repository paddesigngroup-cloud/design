"""create params table

Revision ID: 20260315_0010
Revises: 20260315_0009
Create Date: 2026-03-15 08:45:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260315_0010"
down_revision = "20260315_0009"
branch_labels = None
depends_on = None


PARAM_SEED_ROWS = [
    {"admin_id": None, "param_id": 1, "part_kind_id": 1, "param_code": "w", "param_title_en": "width", "param_title_fa": "عرض", "param_group_id": 1, "ui_order": 1, "code": "w", "title": "عرض", "sort_order": 1, "is_system": True},
    {"admin_id": None, "param_id": 2, "part_kind_id": 1, "param_code": "d", "param_title_en": "depth", "param_title_fa": "عمق", "param_group_id": 1, "ui_order": 2, "code": "d", "title": "عمق", "sort_order": 2, "is_system": True},
    {"admin_id": None, "param_id": 3, "part_kind_id": 1, "param_code": "h", "param_title_en": "height", "param_title_fa": "ارتفاع", "param_group_id": 1, "ui_order": 3, "code": "h", "title": "ارتفاع", "sort_order": 3, "is_system": True},
    {"admin_id": None, "param_id": 4, "part_kind_id": 1, "param_code": "u_f_o", "param_title_en": "unit_floor_offset", "param_title_fa": "فاصله_یونیت_از_کف", "param_group_id": 1, "ui_order": 4, "code": "u_f_o", "title": "فاصله_یونیت_از_کف", "sort_order": 4, "is_system": True},
    {"admin_id": None, "param_id": 5, "part_kind_id": 1, "param_code": "u_th", "param_title_en": "unit_thickness", "param_title_fa": "ضخامت_یونیت", "param_group_id": 2, "ui_order": 1, "code": "u_th", "title": "ضخامت_یونیت", "sort_order": 5, "is_system": True},
    {"admin_id": None, "param_id": 6, "part_kind_id": 1, "param_code": "b_th", "param_title_en": "back_thickness", "param_title_fa": "ضخامت_پشت", "param_group_id": 2, "ui_order": 2, "code": "b_th", "title": "ضخامت_پشت", "sort_order": 6, "is_system": True},
    {"admin_id": None, "param_id": 7, "part_kind_id": 1, "param_code": "l_fl", "param_title_en": "left_floor", "param_title_fa": "کف_چپ", "param_group_id": 3, "ui_order": 1, "code": "l_fl", "title": "کف_چپ", "sort_order": 7, "is_system": True},
    {"admin_id": None, "param_id": 8, "part_kind_id": 1, "param_code": "r_fl", "param_title_en": "right_floor", "param_title_fa": "کف_راست", "param_group_id": 3, "ui_order": 2, "code": "r_fl", "title": "کف_راست", "sort_order": 8, "is_system": True},
    {"admin_id": None, "param_id": 9, "part_kind_id": 1, "param_code": "p_f_f", "param_title_en": "push_front_floor", "param_title_fa": "جلو_دادن_جلوی_کف", "param_group_id": 3, "ui_order": 3, "code": "p_f_f", "title": "جلو_دادن_جلوی_کف", "sort_order": 9, "is_system": True},
    {"admin_id": None, "param_id": 10, "part_kind_id": 1, "param_code": "p_b_f", "param_title_en": "push_back_floor", "param_title_fa": "جلو_دادن_عقب_کف", "param_group_id": 3, "ui_order": 4, "code": "p_b_f", "title": "جلو_دادن_عقب_کف", "sort_order": 10, "is_system": True},
    {"admin_id": None, "param_id": 11, "part_kind_id": 1, "param_code": "p_u_f", "param_title_en": "push_up_floor", "param_title_fa": "جلو_دادن_کف_به_بالا", "param_group_id": 3, "ui_order": 5, "code": "p_u_f", "title": "جلو_دادن_کف_به_بالا", "sort_order": 11, "is_system": True},
    {"admin_id": None, "param_id": 12, "part_kind_id": 1, "param_code": "l_ro", "param_title_en": "left_roof", "param_title_fa": "تاقی_چپ", "param_group_id": 4, "ui_order": 1, "code": "l_ro", "title": "تاقی_چپ", "sort_order": 12, "is_system": True},
    {"admin_id": None, "param_id": 13, "part_kind_id": 1, "param_code": "r_ro", "param_title_en": "right_roof", "param_title_fa": "تاقی_راست", "param_group_id": 4, "ui_order": 2, "code": "r_ro", "title": "تاقی_راست", "sort_order": 13, "is_system": True},
    {"admin_id": None, "param_id": 14, "part_kind_id": 1, "param_code": "p_f_r", "param_title_en": "push_front_roof", "param_title_fa": "جلو_دادن_جلوی_تاق", "param_group_id": 4, "ui_order": 3, "code": "p_f_r", "title": "جلو_دادن_جلوی_تاق", "sort_order": 14, "is_system": True},
    {"admin_id": None, "param_id": 15, "part_kind_id": 1, "param_code": "p_b_r", "param_title_en": "push_back_roof", "param_title_fa": "جلو_دادن_عقب_تاق", "param_group_id": 4, "ui_order": 4, "code": "p_b_r", "title": "جلو_دادن_عقب_تاق", "sort_order": 15, "is_system": True},
    {"admin_id": None, "param_id": 16, "part_kind_id": 1, "param_code": "p_d_r", "param_title_en": "push_down_roof", "param_title_fa": "جلو_دادن_تاق_به_پایین", "param_group_id": 4, "ui_order": 5, "code": "p_d_r", "title": "جلو_دادن_تاق_به_پایین", "sort_order": 16, "is_system": True},
    {"admin_id": None, "param_id": 17, "part_kind_id": 1, "param_code": "b_l_s", "param_title_en": "bottom_left_side", "param_title_fa": "بدنه_چپ_پایین", "param_group_id": 5, "ui_order": 1, "code": "b_l_s", "title": "بدنه_چپ_پایین", "sort_order": 17, "is_system": True},
    {"admin_id": None, "param_id": 18, "part_kind_id": 1, "param_code": "b_r_s", "param_title_en": "bottom_right_side", "param_title_fa": "بدنه_راست_پایین", "param_group_id": 6, "ui_order": 1, "code": "b_r_s", "title": "بدنه_راست_پایین", "sort_order": 18, "is_system": True},
    {"admin_id": None, "param_id": 19, "part_kind_id": 1, "param_code": "t_l_s", "param_title_en": "top_left_side", "param_title_fa": "بدنه_چپ_بالا", "param_group_id": 5, "ui_order": 2, "code": "t_l_s", "title": "بدنه_چپ_بالا", "sort_order": 19, "is_system": True},
    {"admin_id": None, "param_id": 20, "part_kind_id": 1, "param_code": "p_f_ls", "param_title_en": "push_front_left_side", "param_title_fa": "جلو_دادن_جلوی_بدنه_چپ", "param_group_id": 5, "ui_order": 3, "code": "p_f_ls", "title": "جلو_دادن_جلوی_بدنه_چپ", "sort_order": 20, "is_system": True},
    {"admin_id": None, "param_id": 21, "part_kind_id": 1, "param_code": "p_b_ls", "param_title_en": "push_back_left_side", "param_title_fa": "جلو_دادن_عقب_بدنه_چپ", "param_group_id": 5, "ui_order": 4, "code": "p_b_ls", "title": "جلو_دادن_عقب_بدنه_چپ", "sort_order": 21, "is_system": True},
    {"admin_id": None, "param_id": 22, "part_kind_id": 1, "param_code": "ls_t_k", "param_title_en": "left_side_toe_kick", "param_title_fa": "پاسنگ_بدنه_چپ", "param_group_id": 5, "ui_order": 5, "code": "ls_t_k", "title": "پاسنگ_بدنه_چپ", "sort_order": 22, "is_system": True},
    {"admin_id": None, "param_id": 23, "part_kind_id": 1, "param_code": "t_r_s", "param_title_en": "top_right_side", "param_title_fa": "بدنه_راست_بالا", "param_group_id": 6, "ui_order": 2, "code": "t_r_s", "title": "بدنه_راست_بالا", "sort_order": 23, "is_system": True},
    {"admin_id": None, "param_id": 24, "part_kind_id": 1, "param_code": "p_f_rs", "param_title_en": "push_front_right_side", "param_title_fa": "جلو_دادن_جلوی_بدنه_راست", "param_group_id": 6, "ui_order": 3, "code": "p_f_rs", "title": "جلو_دادن_جلوی_بدنه_راست", "sort_order": 24, "is_system": True},
    {"admin_id": None, "param_id": 25, "part_kind_id": 1, "param_code": "p_b_rs", "param_title_en": "push_back_right_side", "param_title_fa": "جلو_دادن_عقب_بدنه_راست", "param_group_id": 6, "ui_order": 4, "code": "p_b_rs", "title": "جلو_دادن_عقب_بدنه_راست", "sort_order": 25, "is_system": True},
    {"admin_id": None, "param_id": 26, "part_kind_id": 1, "param_code": "rs_t_k", "param_title_en": "right_side_toe_kick", "param_title_fa": "پاسنگ_بدنه_راست", "param_group_id": 6, "ui_order": 5, "code": "rs_t_k", "title": "پاسنگ_بدنه_راست", "sort_order": 26, "is_system": True},
    {"admin_id": None, "param_id": 27, "part_kind_id": 1, "param_code": "b_th_ca", "param_title_en": "back_thickness_calculation", "param_title_fa": "محاسبه_ضخامت_پشت", "param_group_id": 8, "ui_order": 1, "code": "b_th_ca", "title": "محاسبه_ضخامت_پشت", "sort_order": 27, "is_system": True},
    {"admin_id": None, "param_id": 28, "part_kind_id": 1, "param_code": "pu_b", "param_title_en": "push_back", "param_title_fa": "جلو_دادن_پشت", "param_group_id": 8, "ui_order": 2, "code": "pu_b", "title": "جلو_دادن_پشت", "sort_order": 28, "is_system": True},
    {"admin_id": None, "param_id": 29, "part_kind_id": 1, "param_code": "b_l_r", "param_title_en": "back_left_reducing", "param_title_fa": "کسر_چپ_پشت", "param_group_id": 8, "ui_order": 3, "code": "b_l_r", "title": "کسر_چپ_پشت", "sort_order": 29, "is_system": True},
    {"admin_id": None, "param_id": 30, "part_kind_id": 1, "param_code": "b_r_r", "param_title_en": "back_right_reducing", "param_title_fa": "کسر_راست_پشت", "param_group_id": 8, "ui_order": 4, "code": "b_r_r", "title": "کسر_راست_پشت", "sort_order": 30, "is_system": True},
    {"admin_id": None, "param_id": 31, "part_kind_id": 1, "param_code": "b_b_r", "param_title_en": "back_bottom_reducing", "param_title_fa": "کسر_پایین_پشت", "param_group_id": 8, "ui_order": 5, "code": "b_b_r", "title": "کسر_پایین_پشت", "sort_order": 31, "is_system": True},
    {"admin_id": None, "param_id": 32, "part_kind_id": 1, "param_code": "b_t_r", "param_title_en": "back_top_reducing", "param_title_fa": "کسر_بالا_پشت", "param_group_id": 8, "ui_order": 6, "code": "b_t_r", "title": "کسر_بالا_پشت", "sort_order": 32, "is_system": True},
    {"admin_id": None, "param_id": 33, "part_kind_id": 1, "param_code": "le_g", "param_title_en": "left_gap", "param_title_fa": "گپ_چپ", "param_group_id": 10, "ui_order": 1, "code": "le_g", "title": "گپ_چپ", "sort_order": 33, "is_system": True},
    {"admin_id": None, "param_id": 34, "part_kind_id": 1, "param_code": "ri_g", "param_title_en": "right_gap", "param_title_fa": "گپ_راست", "param_group_id": 10, "ui_order": 2, "code": "ri_g", "title": "گپ_راست", "sort_order": 34, "is_system": True},
    {"admin_id": None, "param_id": 35, "part_kind_id": 1, "param_code": "fr_g", "param_title_en": "front_gap", "param_title_fa": "گپ_جلو", "param_group_id": 10, "ui_order": 3, "code": "fr_g", "title": "گپ_جلو", "sort_order": 35, "is_system": True},
    {"admin_id": None, "param_id": 36, "part_kind_id": 1, "param_code": "ba_g", "param_title_en": "back_gap", "param_title_fa": "گپ_عقب", "param_group_id": 10, "ui_order": 4, "code": "ba_g", "title": "گپ_عقب", "sort_order": 36, "is_system": True},
    {"admin_id": None, "param_id": 37, "part_kind_id": 1, "param_code": "bo_g", "param_title_en": "bottom_gap", "param_title_fa": "گپ_پایین", "param_group_id": 10, "ui_order": 5, "code": "bo_g", "title": "گپ_پایین", "sort_order": 37, "is_system": True},
    {"admin_id": None, "param_id": 38, "part_kind_id": 1, "param_code": "to_g", "param_title_en": "top_gap", "param_title_fa": "گپ_بالا", "param_group_id": 10, "ui_order": 6, "code": "to_g", "title": "گپ_بالا", "sort_order": 38, "is_system": True},
    {"admin_id": None, "param_id": 39, "part_kind_id": 2, "param_code": "w_st", "param_title_en": "width_stretcher", "param_title_fa": "عرض_تیرک", "param_group_id": 12, "ui_order": 1, "code": "w_st", "title": "عرض_تیرک", "sort_order": 39, "is_system": True},
    {"admin_id": None, "param_id": 40, "part_kind_id": 2, "param_code": "l_to_fr_h_st", "param_title_en": "left_top_front_horizontal_stretcher", "param_title_fa": "تیرک_افقی_جلو_بالا_چپ", "param_group_id": 12, "ui_order": 2, "code": "l_to_fr_h_st", "title": "تیرک_افقی_جلو_بالا_چپ", "sort_order": 40, "is_system": True},
    {"admin_id": None, "param_id": 41, "part_kind_id": 2, "param_code": "r_to_fr_h_st", "param_title_en": "right_top_front_horizontal_stretcher", "param_title_fa": "تیرک_افقی_جلو_بالا_راست", "param_group_id": 12, "ui_order": 3, "code": "r_to_fr_h_st", "title": "تیرک_افقی_جلو_بالا_راست", "sort_order": 41, "is_system": True},
    {"admin_id": None, "param_id": 42, "part_kind_id": 2, "param_code": "p_f_to_fr_h_st", "param_title_en": "push_front_top_front_horizontal_stretcher", "param_title_fa": "جلو_دادن_جلوی_تیرک_افقی_جلو_بالا", "param_group_id": 12, "ui_order": 4, "code": "p_f_to_fr_h_st", "title": "جلو_دادن_جلوی_تیرک_افقی_جلو_بالا", "sort_order": 42, "is_system": True},
    {"admin_id": None, "param_id": 43, "part_kind_id": 2, "param_code": "p_d_to_fr_h_st", "param_title_en": "push_down_top_front_horizontal_stretcher", "param_title_fa": "جلو_دادن_تیرک_افقی_جلو_بالا_به_پایین", "param_group_id": 12, "ui_order": 5, "code": "p_d_to_fr_h_st", "title": "جلو_دادن_تیرک_افقی_جلو_بالا_به_پایین", "sort_order": 43, "is_system": True},
    {"admin_id": None, "param_id": 44, "part_kind_id": 2, "param_code": "l_to_ba_h_st", "param_title_en": "left_top_back_horizontal_stretcher", "param_title_fa": "تیرک_افقی_عقب_بالا_چپ", "param_group_id": 12, "ui_order": 6, "code": "l_to_ba_h_st", "title": "تیرک_افقی_عقب_بالا_چپ", "sort_order": 44, "is_system": True},
    {"admin_id": None, "param_id": 45, "part_kind_id": 2, "param_code": "r_to_ba_h_st", "param_title_en": "right_top_back_horizontal_stretcher", "param_title_fa": "تیرک_افقی_عقب_بالا_راست", "param_group_id": 12, "ui_order": 7, "code": "r_to_ba_h_st", "title": "تیرک_افقی_عقب_بالا_راست", "sort_order": 45, "is_system": True},
    {"admin_id": None, "param_id": 46, "part_kind_id": 2, "param_code": "p_b_to_ba_h_st", "param_title_en": "push_back_top_back_horizontal_stretcher", "param_title_fa": "جلو_دادن_عقب_تیرک_افقی_عقب_بالا", "param_group_id": 12, "ui_order": 8, "code": "p_b_to_ba_h_st", "title": "جلو_دادن_عقب_تیرک_افقی_عقب_بالا", "sort_order": 46, "is_system": True},
    {"admin_id": None, "param_id": 47, "part_kind_id": 2, "param_code": "p_d_to_ba_h_st", "param_title_en": "push_down_top_back_horizontal_stretcher", "param_title_fa": "جلو_دادن_تیرک_افقی_عقب_بالا_به_پایین", "param_group_id": 12, "ui_order": 9, "code": "p_d_to_ba_h_st", "title": "جلو_دادن_تیرک_افقی_عقب_بالا_به_پایین", "sort_order": 47, "is_system": True},
    {"admin_id": None, "param_id": 48, "part_kind_id": 2, "param_code": "l_to_v_st", "param_title_en": "left_top_vertical_stretcher", "param_title_fa": "تیرک_عمودی_پشت_بالا_چپ", "param_group_id": 12, "ui_order": 10, "code": "l_to_v_st", "title": "تیرک_عمودی_پشت_بالا_چپ", "sort_order": 48, "is_system": True},
    {"admin_id": None, "param_id": 49, "part_kind_id": 2, "param_code": "r_to_v_st", "param_title_en": "right_top_vertical_stretcher", "param_title_fa": "تیرک_عمودی_پشت_بالا_راست", "param_group_id": 12, "ui_order": 11, "code": "r_to_v_st", "title": "تیرک_عمودی_پشت_بالا_راست", "sort_order": 49, "is_system": True},
    {"admin_id": None, "param_id": 50, "part_kind_id": 2, "param_code": "p_b_to_v_st", "param_title_en": "push_back_top_vertical_stretcher", "param_title_fa": "جلو_دادن_عقب_تیرک_عمودی_پشت_بالا", "param_group_id": 12, "ui_order": 12, "code": "p_b_to_v_st", "title": "جلو_دادن_عقب_تیرک_عمودی_پشت_بالا", "sort_order": 50, "is_system": True},
    {"admin_id": None, "param_id": 51, "part_kind_id": 2, "param_code": "p_d_to_v_st", "param_title_en": "push_down_top_vertical_stretcher", "param_title_fa": "جلو_دادن_تیرک_عمودی_پشت_بالا_به_پایین", "param_group_id": 12, "ui_order": 13, "code": "p_d_to_v_st", "title": "جلو_دادن_تیرک_عمودی_پشت_بالا_به_پایین", "sort_order": 51, "is_system": True},
    {"admin_id": None, "param_id": 52, "part_kind_id": 2, "param_code": "l_bo_v_st", "param_title_en": "left_bottom_vertical_stretcher", "param_title_fa": "تیرک_عمودی_پشت_پایین_چپ", "param_group_id": 12, "ui_order": 14, "code": "l_bo_v_st", "title": "تیرک_عمودی_پشت_پایین_چپ", "sort_order": 52, "is_system": True},
    {"admin_id": None, "param_id": 53, "part_kind_id": 2, "param_code": "r_bo_v_st", "param_title_en": "right_bottom_vertical_stretcher", "param_title_fa": "تیرک_عمودی_پشت_پایین_راست", "param_group_id": 12, "ui_order": 15, "code": "r_bo_v_st", "title": "تیرک_عمودی_پشت_پایین_راست", "sort_order": 53, "is_system": True},
    {"admin_id": None, "param_id": 54, "part_kind_id": 2, "param_code": "p_b_bo_v_st", "param_title_en": "push_back_bottom_vertical_stretcher", "param_title_fa": "جلو_دادن_عقب_تیرک_عمودی_پشت_پایین", "param_group_id": 12, "ui_order": 16, "code": "p_b_bo_v_st", "title": "جلو_دادن_عقب_تیرک_عمودی_پشت_پایین", "sort_order": 54, "is_system": True},
    {"admin_id": None, "param_id": 55, "part_kind_id": 2, "param_code": "p_u_bo_v_st", "param_title_en": "push_up_bottom_vertical_stretcher", "param_title_fa": "جلو_دادن_تیرک_عمودی_پشت_پایین_به_بالا", "param_group_id": 12, "ui_order": 17, "code": "p_u_bo_v_st", "title": "جلو_دادن_تیرک_عمودی_پشت_پایین_به_بالا", "sort_order": 55, "is_system": True},
    {"admin_id": None, "param_id": 56, "part_kind_id": 6, "param_code": "d_th", "param_title_en": "door_thickness", "param_title_fa": "ضخامت_درب", "param_group_id": 2, "ui_order": 3, "code": "d_th", "title": "ضخامت_درب", "sort_order": 56, "is_system": True},
    {"admin_id": None, "param_id": 57, "part_kind_id": 6, "param_code": "f_th", "param_title_en": "frame_thickness", "param_title_fa": "ضخامت_قاب", "param_group_id": 2, "ui_order": 4, "code": "f_th", "title": "ضخامت_قاب", "sort_order": 57, "is_system": True},
    {"admin_id": None, "param_id": 58, "part_kind_id": 6, "param_code": "d_th_ca", "param_title_en": "door_thickness_calculation", "param_title_fa": "محاسبه_ضخامت_درب", "param_group_id": 7, "ui_order": 1, "code": "d_th_ca", "title": "محاسبه_ضخامت_درب", "sort_order": 58, "is_system": True},
    {"admin_id": None, "param_id": 59, "part_kind_id": 6, "param_code": "f_th_ca", "param_title_en": "frame_thickness_calculation", "param_title_fa": "محاسبه_ضخامت_قاب", "param_group_id": 7, "ui_order": 2, "code": "f_th_ca", "title": "محاسبه_ضخامت_قاب", "sort_order": 59, "is_system": True},
    {"admin_id": None, "param_id": 60, "part_kind_id": 6, "param_code": "pu_d", "param_title_en": "push_door", "param_title_fa": "جلو_دادن_درب", "param_group_id": 7, "ui_order": 3, "code": "pu_d", "title": "جلو_دادن_درب", "sort_order": 60, "is_system": True},
    {"admin_id": None, "param_id": 61, "part_kind_id": 6, "param_code": "d_l_r", "param_title_en": "door_left_reducing", "param_title_fa": "کسر_چپ_درب", "param_group_id": 7, "ui_order": 4, "code": "d_l_r", "title": "کسر_چپ_درب", "sort_order": 61, "is_system": True},
    {"admin_id": None, "param_id": 62, "part_kind_id": 6, "param_code": "d_r_r", "param_title_en": "door_right_reducing", "param_title_fa": "کسر_راست_درب", "param_group_id": 7, "ui_order": 5, "code": "d_r_r", "title": "کسر_راست_درب", "sort_order": 62, "is_system": True},
    {"admin_id": None, "param_id": 63, "part_kind_id": 6, "param_code": "d_b_r", "param_title_en": "door_bottom_reducing", "param_title_fa": "کسر_پایین_درب", "param_group_id": 7, "ui_order": 6, "code": "d_b_r", "title": "کسر_پایین_درب", "sort_order": 63, "is_system": True},
    {"admin_id": None, "param_id": 64, "part_kind_id": 6, "param_code": "d_t_r", "param_title_en": "door_top_reducing", "param_title_fa": "کسر_بالا_درب", "param_group_id": 7, "ui_order": 7, "code": "d_t_r", "title": "کسر_بالا_درب", "sort_order": 64, "is_system": True},
    {"admin_id": None, "param_id": 65, "part_kind_id": 7, "param_code": "p_th", "param_title_en": "panel_thickness", "param_title_fa": "ضخامت_نما", "param_group_id": 2, "ui_order": 5, "code": "p_th", "title": "ضخامت_نما", "sort_order": 65, "is_system": True},
    {"admin_id": None, "param_id": 66, "part_kind_id": 7, "param_code": "le_p", "param_title_en": "left_panel", "param_title_fa": "نما_چپ", "param_group_id": 9, "ui_order": 1, "code": "le_p", "title": "نما_چپ", "sort_order": 66, "is_system": True},
    {"admin_id": None, "param_id": 67, "part_kind_id": 7, "param_code": "ri_p", "param_title_en": "right_panel", "param_title_fa": "نما_راست", "param_group_id": 9, "ui_order": 2, "code": "ri_p", "title": "نما_راست", "sort_order": 67, "is_system": True},
    {"admin_id": None, "param_id": 68, "part_kind_id": 7, "param_code": "fr_p", "param_title_en": "front_panel", "param_title_fa": "نما_جلو", "param_group_id": 9, "ui_order": 3, "code": "fr_p", "title": "نما_جلو", "sort_order": 68, "is_system": True},
    {"admin_id": None, "param_id": 69, "part_kind_id": 7, "param_code": "ba_p", "param_title_en": "back_panel", "param_title_fa": "نما_پشت", "param_group_id": 9, "ui_order": 4, "code": "ba_p", "title": "نما_پشت", "sort_order": 69, "is_system": True},
    {"admin_id": None, "param_id": 70, "part_kind_id": 7, "param_code": "bo_p", "param_title_en": "bottom_panel", "param_title_fa": "نما_پایین", "param_group_id": 9, "ui_order": 5, "code": "bo_p", "title": "نما_پایین", "sort_order": 70, "is_system": True},
    {"admin_id": None, "param_id": 71, "part_kind_id": 7, "param_code": "to_p", "param_title_en": "top_panel", "param_title_fa": "نما_بالا", "param_group_id": 9, "ui_order": 6, "code": "to_p", "title": "نما_بالا", "sort_order": 71, "is_system": True},
    {"admin_id": None, "param_id": 72, "part_kind_id": 10, "param_code": "c_th", "param_title_en": "counter_thickness", "param_title_fa": "ضخامت_صفحه", "param_group_id": 2, "ui_order": 6, "code": "c_th", "title": "ضخامت_صفحه", "sort_order": 72, "is_system": True},
    {"admin_id": None, "param_id": 73, "part_kind_id": 10, "param_code": "c_g", "param_title_en": "counter_offset", "param_title_fa": "فاصله_صفحه", "param_group_id": 11, "ui_order": 1, "code": "c_g", "title": "فاصله_صفحه", "sort_order": 73, "is_system": True},
    {"admin_id": None, "param_id": 74, "part_kind_id": 10, "param_code": "le_n", "param_title_en": "left_nosecounter", "param_title_fa": "دماغه_صفحه_چپ", "param_group_id": 11, "ui_order": 2, "code": "le_n", "title": "دماغه_صفحه_چپ", "sort_order": 74, "is_system": True},
    {"admin_id": None, "param_id": 75, "part_kind_id": 10, "param_code": "ri_n", "param_title_en": "right_nosecounter", "param_title_fa": "دماغه_صفحه_راست", "param_group_id": 11, "ui_order": 3, "code": "ri_n", "title": "دماغه_صفحه_راست", "sort_order": 75, "is_system": True},
    {"admin_id": None, "param_id": 76, "part_kind_id": 10, "param_code": "fr_n", "param_title_en": "front_nosecounter", "param_title_fa": "دماغه_صفحه_جلو", "param_group_id": 11, "ui_order": 4, "code": "fr_n", "title": "دماغه_صفحه_جلو", "sort_order": 76, "is_system": True},
    {"admin_id": None, "param_id": 77, "part_kind_id": 10, "param_code": "ba_n", "param_title_en": "back_nosecounter", "param_title_fa": "دماغه_صفحه_عقب", "param_group_id": 11, "ui_order": 5, "code": "ba_n", "title": "دماغه_صفحه_عقب", "sort_order": 77, "is_system": True},
]


def upgrade() -> None:
    op.create_table(
        "params",
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("param_id", sa.Integer(), nullable=True),
        sa.Column("part_kind_id", sa.Integer(), nullable=False),
        sa.Column("param_code", sa.String(length=64), nullable=False),
        sa.Column("param_title_en", sa.String(length=255), nullable=False),
        sa.Column("param_title_fa", sa.String(length=255), nullable=False),
        sa.Column("param_group_id", sa.Integer(), nullable=False),
        sa.Column("ui_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], name=op.f("fk_params_admin_id_admins"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["part_kind_id"], ["part_kinds.part_kind_id"], name=op.f("fk_params_part_kind_id_part_kinds"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["param_group_id"], ["param_groups.param_group_id"], name=op.f("fk_params_param_group_id_param_groups"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_params")),
        sa.UniqueConstraint("param_id", name=op.f("uq_params_param_id")),
        sa.UniqueConstraint("part_kind_id", "param_code", name=op.f("uq_params_part_kind_id_param_code")),
    )
    op.create_index(op.f("ix_params_admin_id"), "params", ["admin_id"], unique=False)
    op.create_index(op.f("ix_params_param_id"), "params", ["param_id"], unique=False)
    op.create_index(op.f("ix_params_part_kind_id"), "params", ["part_kind_id"], unique=False)
    op.create_index(op.f("ix_params_param_group_id"), "params", ["param_group_id"], unique=False)

    params_table = sa.table(
        "params",
        sa.column("admin_id", postgresql.UUID(as_uuid=True)),
        sa.column("param_id", sa.Integer()),
        sa.column("part_kind_id", sa.Integer()),
        sa.column("param_code", sa.String(length=64)),
        sa.column("param_title_en", sa.String(length=255)),
        sa.column("param_title_fa", sa.String(length=255)),
        sa.column("param_group_id", sa.Integer()),
        sa.column("ui_order", sa.Integer()),
        sa.column("code", sa.String(length=64)),
        sa.column("title", sa.String(length=255)),
        sa.column("sort_order", sa.Integer()),
        sa.column("is_system", sa.Boolean()),
    )
    op.bulk_insert(params_table, PARAM_SEED_ROWS)


def downgrade() -> None:
    op.drop_index(op.f("ix_params_param_group_id"), table_name="params")
    op.drop_index(op.f("ix_params_part_kind_id"), table_name="params")
    op.drop_index(op.f("ix_params_param_id"), table_name="params")
    op.drop_index(op.f("ix_params_admin_id"), table_name="params")
    op.drop_table("params")
