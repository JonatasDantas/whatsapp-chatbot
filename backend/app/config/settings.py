import os

import boto3

_settings = None


class Settings:
    def __init__(self):
        self.openai_model: str = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

        param_names = {
            "openai_api_key": os.environ["OPENAI_API_KEY_PARAM"],
            "whatsapp_access_token": os.environ["WHATSAPP_ACCESS_TOKEN_PARAM"],
            "whatsapp_phone_number_id": os.environ["WHATSAPP_PHONE_NUMBER_ID_PARAM"],
            "knowledge_base_bucket": os.environ["KNOWLEDGE_BASE_BUCKET_PARAM"],
        }

        ssm = boto3.client("ssm")
        response = ssm.get_parameters(
            Names=list(param_names.values()),
            WithDecryption=True,
        )

        values = {p["Name"]: p["Value"] for p in response["Parameters"]}

        for attr, param_name in param_names.items():
            if param_name not in values:
                raise ValueError(f"SSM parameter not found or inaccessible: {param_name}")
            setattr(self, attr, values[param_name])


def _get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
