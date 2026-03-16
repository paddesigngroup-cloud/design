from designkp_backend.api.formula_validation import validate_formula_structure


def test_validate_formula_structure_allows_negative_decimal_identifiers_mix() -> None:
    assert validate_formula_structure("(w-f1)+(-2.5)") == []


def test_validate_formula_structure_rejects_invalid_order() -> None:
    assert validate_formula_structure("w(f1)") == ["Formula contains invalid token order."]
