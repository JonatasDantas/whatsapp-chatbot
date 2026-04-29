from decimal import Decimal
from app.utils.dynamodb import to_dynamodb_item


def test_converts_float_to_decimal():
    result = to_dynamodb_item({"price": 1600.0})
    assert result["price"] == Decimal("1600.0")
    assert isinstance(result["price"], Decimal)


def test_removes_none_values():
    result = to_dynamodb_item({"name": "Ana", "checkout": None})
    assert "checkout" not in result
    assert result["name"] == "Ana"


def test_preserves_int_and_bool():
    result = to_dynamodb_item({"guests": 4, "rules_accepted": True})
    assert result["guests"] == 4
    assert result["rules_accepted"] is True


def test_preserves_strings():
    result = to_dynamodb_item({"phone_number": "+5511999999999", "stage": "greeting"})
    assert result["phone_number"] == "+5511999999999"


def test_nested_dict_converted():
    result = to_dynamodb_item({"meta": {"rate": 800.0, "label": None}})
    assert result["meta"]["rate"] == Decimal("800.0")
    assert "label" not in result["meta"]


def test_empty_dict():
    assert to_dynamodb_item({}) == {}
