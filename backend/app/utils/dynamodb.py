"""DynamoDB serialization helpers."""
from decimal import Decimal


def to_dynamodb_item(data: dict) -> dict:
    """
    Convert a dict (from Pydantic model_dump) into a DynamoDB-compatible item.

    DynamoDB rejects Python float values; they must be Decimal.
    None values are removed because DynamoDB cannot store them as attributes.
    """
    result = {}
    for key, value in data.items():
        if value is None:
            continue
        elif isinstance(value, float):
            result[key] = Decimal(str(value))
        elif isinstance(value, dict):
            result[key] = to_dynamodb_item(value)
        elif isinstance(value, list):
            result[key] = [
                to_dynamodb_item(v) if isinstance(v, dict) else
                Decimal(str(v)) if isinstance(v, float) else v
                for v in value
            ]
        else:
            result[key] = value
    return result
