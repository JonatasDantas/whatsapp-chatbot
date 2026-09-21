import os

import boto3

_settings = None


class Settings:
    def __init__(self):
        self.openai_model: str = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.openai_api_key: str = ""
        self.evolution_api_url: str = ""
        self.evolution_api_key: str = ""
        self.evolution_instance_name: str = ""
        self.knowledge_base_bucket: str = ""
        self.owner_phone: str = ""

        param_names = {
            attr: os.environ[env_var]
            for attr, env_var in {
                "openai_api_key": "OPENAI_API_KEY_PARAM",
                "evolution_api_url": "EVOLUTION_API_URL_PARAM",
                "evolution_api_key": "EVOLUTION_API_KEY_PARAM",
                "evolution_instance_name": "EVOLUTION_INSTANCE_NAME_PARAM",
                "knowledge_base_bucket": "KNOWLEDGE_BASE_BUCKET_PARAM",
                "owner_phone": "OWNER_PHONE_PARAM",
            }.items()
            if env_var in os.environ
        }

        if param_names:
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
