# Parameter Store Settings Migration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate `Settings` from reading environment variables to fetching values from AWS SSM Parameter Store, with parameters created and managed by CDK.

**Architecture:** `Settings.__init__` reads four parameter names from env vars, makes one batched `ssm.get_parameters()` call with `WithDecryption=True`, and populates instance attributes. CDK creates all four parameters as `ssm.StringParameter` (String type, CloudFormation does not support SecureString creation) with dummy values. Post-deploy, the operator converts the two secret parameters to SecureString via CLI. The Lambda is granted `ssm:GetParameters` + `kms:Decrypt`.

**Tech Stack:** Python 3.12, boto3 (SSM), AWS CDK (`aws_ssm`, `aws_iam`), pytest, `unittest.mock`

---

## File Map

| File | Change |
|---|---|
| `backend/tests/config/test_settings.py` | Replace all existing tests with SSM-mocked tests |
| `backend/app/config/settings.py` | Replace env var reads with batched SSM fetch |
| `infrastructure/cdk/stacks/backend_stack.py` | Add SSM parameters, env vars, IAM grants |

---

## Chunk 1: Settings — Tests and Implementation

### Task 1: Replace Settings tests

**Files:**
- Modify: `backend/tests/config/test_settings.py`

- [ ] **Step 1: Replace the file with failing tests**

  Replace the entire contents of `backend/tests/config/test_settings.py` with:

  ```python
  import pytest
  from unittest.mock import patch, MagicMock
  from app.config.settings import Settings

  PARAM_NAMES = {
      "OPENAI_API_KEY_PARAM": "/chacara-chatbot/openai-api-key",
      "WHATSAPP_ACCESS_TOKEN_PARAM": "/chacara-chatbot/whatsapp-access-token",
      "WHATSAPP_PHONE_NUMBER_ID_PARAM": "/chacara-chatbot/whatsapp-phone-number-id",
      "KNOWLEDGE_BASE_BUCKET_PARAM": "/chacara-chatbot/knowledge-base-bucket",
  }

  SSM_RESPONSE = {
      "Parameters": [
          {"Name": "/chacara-chatbot/openai-api-key", "Value": "sk-test"},
          {"Name": "/chacara-chatbot/whatsapp-access-token", "Value": "wa-token"},
          {"Name": "/chacara-chatbot/whatsapp-phone-number-id", "Value": "12345"},
          {"Name": "/chacara-chatbot/knowledge-base-bucket", "Value": "my-bucket"},
      ],
      "InvalidParameters": [],
  }


  def _mock_ssm(response=SSM_RESPONSE):
      mock_client = MagicMock()
      mock_client.get_parameters.return_value = response
      return mock_client


  def _set_param_envs(monkeypatch):
      for key, value in PARAM_NAMES.items():
          monkeypatch.setenv(key, value)


  def test_settings_reads_from_ssm(monkeypatch):
      _set_param_envs(monkeypatch)
      monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")

      with patch("app.config.settings.boto3.client", return_value=_mock_ssm()):
          s = Settings()

      assert s.openai_api_key == "sk-test"
      assert s.openai_model == "gpt-4o"
      assert s.whatsapp_access_token == "wa-token"
      assert s.whatsapp_phone_number_id == "12345"
      assert s.knowledge_base_bucket == "my-bucket"


  def test_settings_default_model(monkeypatch):
      _set_param_envs(monkeypatch)
      monkeypatch.delenv("OPENAI_MODEL", raising=False)

      with patch("app.config.settings.boto3.client", return_value=_mock_ssm()):
          s = Settings()

      assert s.openai_model == "gpt-4o-mini"


  def test_settings_raises_on_missing_parameter(monkeypatch):
      _set_param_envs(monkeypatch)
      response_missing_one = {
          "Parameters": [
              {"Name": "/chacara-chatbot/openai-api-key", "Value": "sk-test"},
              # whatsapp-access-token intentionally missing
              {"Name": "/chacara-chatbot/whatsapp-phone-number-id", "Value": "12345"},
              {"Name": "/chacara-chatbot/knowledge-base-bucket", "Value": "my-bucket"},
          ],
          "InvalidParameters": ["/chacara-chatbot/whatsapp-access-token"],
      }

      with patch("app.config.settings.boto3.client", return_value=_mock_ssm(response_missing_one)):
          with pytest.raises(ValueError, match="/chacara-chatbot/whatsapp-access-token"):
              Settings()
  ```

- [ ] **Step 2: Run tests to confirm they fail**

  ```bash
  cd /path/to/repo && pytest backend/tests/config/test_settings.py -v
  ```

  Expected: all 3 tests **FAIL** — `ImportError` or `AttributeError` because `Settings` still reads env vars.

---

### Task 2: Implement Settings with SSM fetch

**Files:**
- Modify: `backend/app/config/settings.py`

- [ ] **Step 3: Replace the Settings implementation**

  Replace the entire contents of `backend/app/config/settings.py` with:

  ```python
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
  ```

- [ ] **Step 4: Run tests to confirm they pass**

  ```bash
  pytest backend/tests/config/test_settings.py -v
  ```

  Expected: all 3 tests **PASS**.

- [ ] **Step 5: Run the full test suite to check for regressions**

  ```bash
  pytest --tb=short -q
  ```

  Expected: no new failures. (Tests that previously relied on `OPENAI_API_KEY` env var being set will now fail if they import `_get_settings` at module level — fix any such import-time side effects if found.)

- [ ] **Step 6: Commit**

  ```bash
  git add backend/app/config/settings.py backend/tests/config/test_settings.py
  git commit -m "feat: fetch settings from SSM Parameter Store"
  ```

---

## Chunk 2: CDK — Parameters and IAM

> **CloudFormation limitation:** `AWS::SSM::Parameter` only supports `String` and `StringList` types — not `SecureString`. All four parameters are created as `String` with a placeholder value. After deploy, the operator converts the two secret parameters to `SecureString` via the AWS CLI (see Operational Note).

### Task 3: Add SSM parameters and Lambda permissions in CDK

**Files:**
- Modify: `infrastructure/cdk/stacks/backend_stack.py`

- [ ] **Step 7: Add `aws_iam` import and a `_create_settings_parameters` method**

  At the top of `backend_stack.py`, add `aws_iam` to the imports:

  ```python
  from aws_cdk import aws_iam as iam
  ```

  Add this method to `BackendStack` (place it after `_create_reservations_table`):

  ```python
  def _create_settings_parameters(self) -> tuple:
      openai_key = ssm.StringParameter(
          self,
          "OpenAiApiKeyParam",
          parameter_name="/chacara-chatbot/openai-api-key",
          string_value="REPLACE_ME",
      )
      whatsapp_token = ssm.StringParameter(
          self,
          "WhatsappAccessTokenParam",
          parameter_name="/chacara-chatbot/whatsapp-access-token",
          string_value="REPLACE_ME",
      )
      whatsapp_phone = ssm.StringParameter(
          self,
          "WhatsappPhoneNumberIdParam",
          parameter_name="/chacara-chatbot/whatsapp-phone-number-id",
          string_value="REPLACE_ME",
      )
      knowledge_base = ssm.StringParameter(
          self,
          "KnowledgeBaseBucketParam",
          parameter_name="/chacara-chatbot/knowledge-base-bucket",
          string_value="REPLACE_ME",
      )
      return openai_key, whatsapp_token, whatsapp_phone, knowledge_base
  ```

- [ ] **Step 8: Wire the new parameters into `__init__` and `_create_webhook_function`**

  Update `BackendStack.__init__` to call the new method and pass results to `_create_webhook_function`:

  ```python
  def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
      super().__init__(scope, construct_id, **kwargs)

      conversations_table = self._create_conversations_table()
      messages_table = self._create_messages_table()
      reservations_table = self._create_reservations_table()

      verify_token_param = ssm.StringParameter.from_secure_string_parameter_attributes(
          self,
          "WhatsappVerifyTokenParam",
          parameter_name="/chacara-chatbot/whatsapp-verify-token",
      )

      openai_key_param, whatsapp_token_param, whatsapp_phone_param, knowledge_base_param = (
          self._create_settings_parameters()
      )

      webhook_function = self._create_webhook_function(
          conversations_table,
          messages_table,
          reservations_table,
          verify_token_param,
          openai_key_param,
          whatsapp_token_param,
          whatsapp_phone_param,
          knowledge_base_param,
      )

      self._create_api_gateway(webhook_function)
  ```

- [ ] **Step 9: Update `_create_webhook_function` signature, env vars, and IAM grants**

  Replace the existing `_create_webhook_function` with:

  ```python
  def _create_webhook_function(
      self,
      conversations_table: dynamodb.Table,
      messages_table: dynamodb.Table,
      reservations_table: dynamodb.Table,
      verify_token_param: ssm.IStringParameter,
      openai_key_param: ssm.StringParameter,
      whatsapp_token_param: ssm.StringParameter,
      whatsapp_phone_param: ssm.StringParameter,
      knowledge_base_param: ssm.StringParameter,
  ) -> _lambda.Function:
      powertools_layer = _lambda.LayerVersion.from_layer_version_arn(
          self,
          "PowertoolsLayer",
          f"arn:aws:lambda:{self.region}:017000801446:layer:AWSLambdaPowertoolsPythonV3-python312-x86_64:7",
      )

      function = _lambda.Function(
          self,
          "WebhookFunction",
          runtime=_lambda.Runtime.PYTHON_3_12,
          handler="lambdas.webhook.handler.handler",
          code=_lambda.Code.from_asset("backend"),
          layers=[powertools_layer],
          environment={
              "CONVERSATIONS_TABLE": conversations_table.table_name,
              "MESSAGES_TABLE": messages_table.table_name,
              "RESERVATIONS_TABLE": reservations_table.table_name,
              "WHATSAPP_VERIFY_TOKEN_PARAM": verify_token_param.parameter_name,
              "OPENAI_API_KEY_PARAM": openai_key_param.parameter_name,
              "WHATSAPP_ACCESS_TOKEN_PARAM": whatsapp_token_param.parameter_name,
              "WHATSAPP_PHONE_NUMBER_ID_PARAM": whatsapp_phone_param.parameter_name,
              "KNOWLEDGE_BASE_BUCKET_PARAM": knowledge_base_param.parameter_name,
          },
      )

      conversations_table.grant_read_write_data(function)
      messages_table.grant_read_write_data(function)
      reservations_table.grant_read_write_data(function)
      verify_token_param.grant_read(function)

      # ssm:GetParameters (plural) for the batched get_parameters() call in Settings
      function.add_to_role_policy(
          iam.PolicyStatement(
              actions=["ssm:GetParameters"],
              resources=[
                  openai_key_param.parameter_arn,
                  whatsapp_token_param.parameter_arn,
                  whatsapp_phone_param.parameter_arn,
                  knowledge_base_param.parameter_arn,
              ],
          )
      )
      # Required for WithDecryption=True once the operator converts secret params to SecureString
      function.add_to_role_policy(
          iam.PolicyStatement(
              actions=["kms:Decrypt"],
              resources=[f"arn:aws:kms:{self.region}:{self.account}:alias/aws/ssm"],
          )
      )

      return function
  ```

- [ ] **Step 10: Synthesize CDK to verify no errors**

  ```bash
  cd infrastructure && cdk synth 2>&1 | tail -20
  ```

  Expected: CDK outputs a CloudFormation template with no errors. Verify the output contains four `AWS::SSM::Parameter` resources and an IAM policy granting `ssm:GetParameters` and `kms:Decrypt`.

- [ ] **Step 11: Commit**

  ```bash
  git add infrastructure/cdk/stacks/backend_stack.py
  git commit -m "feat: create SSM parameters in CDK and grant Lambda access"
  ```

---

## Operational Note

After deploying to AWS, update the four SSM parameters with real values. For the two secrets, use `--type SecureString` to encrypt them at rest:

```bash
aws ssm put-parameter --name "/chacara-chatbot/openai-api-key" --value "YOUR_KEY" --type SecureString --overwrite
aws ssm put-parameter --name "/chacara-chatbot/whatsapp-access-token" --value "YOUR_TOKEN" --type SecureString --overwrite
aws ssm put-parameter --name "/chacara-chatbot/whatsapp-phone-number-id" --value "YOUR_PHONE_ID" --type String --overwrite
aws ssm put-parameter --name "/chacara-chatbot/knowledge-base-bucket" --value "YOUR_BUCKET" --type String --overwrite
```

The Lambda will fail until all four parameters contain real values.
