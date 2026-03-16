# Design: Migrate Settings to AWS Parameter Store

**Date:** 2026-03-16
**Status:** Approved

---

## Overview

Migrate sensitive and configuration settings from Lambda environment variables to AWS Systems Manager (SSM) Parameter Store. Values are fetched at Lambda cold start via a single batched boto3 SSM API call and cached for the lifetime of the container.

`OPENAI_MODEL` remains an environment variable (not a secret, changes require redeploy anyway).

---

## Parameters

Naming convention for the four new parameters: `/chacara-chatbot/{param-name}` (flat). The existing verify token parameter (`/chacara-chatbot/whatsapp-verify-token` or `/chacara-chatbot/whatsapp/verify-token` depending on runtime vs CDK reference) retains its existing name and is not renamed.

All four parameters are created by CDK using `ssm.StringParameter` (String type) with the dummy value `"REPLACE_ME"`.

> **CloudFormation limitation:** CloudFormation's `AWS::SSM::Parameter` resource (and therefore CDK's `ssm.StringParameter` and `ssm.CfnParameter`) does not support creating `SecureString` parameters. All four are created as `String` type.

| Attribute | SSM Parameter Name | CDK Construct |
|---|---|---|
| `openai_api_key` | `/chacara-chatbot/openai-api-key` | `ssm.StringParameter` |
| `whatsapp_access_token` | `/chacara-chatbot/whatsapp-access-token` | `ssm.StringParameter` |
| `whatsapp_phone_number_id` | `/chacara-chatbot/whatsapp-phone-number-id` | `ssm.StringParameter` |
| `knowledge_base_bucket` | `/chacara-chatbot/knowledge-base-bucket` | `ssm.StringParameter` |

**Operational note:** After the first deploy, the operator must:
1. Update all four parameters with real values.
2. For `openai_api_key` and `whatsapp_access_token`, convert to SecureString using the CLI:
   ```bash
   aws ssm put-parameter --name "/chacara-chatbot/openai-api-key" --value "REAL_KEY" --type SecureString --overwrite
   ```
   Once converted to SecureString, the Lambda's `kms:Decrypt` grant handles decryption automatically.

---

## CDK Changes (`infrastructure/cdk/stacks/backend_stack.py`)

1. Create four SSM parameters using the constructs listed above.
2. Pass each parameter's **name** to the Lambda as an environment variable:
   - `OPENAI_API_KEY_PARAM`
   - `WHATSAPP_ACCESS_TOKEN_PARAM`
   - `WHATSAPP_PHONE_NUMBER_ID_PARAM`
   - `KNOWLEDGE_BASE_BUCKET_PARAM`
3. Grant the Lambda IAM permissions:
   - `ssm:GetParameters` on the ARNs of all four parameters — added via `function.add_to_role_policy(iam.PolicyStatement(...))` since `ssm.StringParameter.grant_read()` only grants the singular `ssm:GetParameter` action.
   - `kms:Decrypt` on `arn:aws:kms:{region}:{account}:alias/aws/ssm` — required once the operator converts the secret parameters to SecureString post-deploy.

---

## Settings Changes (`backend/app/config/settings.py`)

`Settings.__init__` is updated to:

1. Read the four parameter names from environment variables.
2. Create a boto3 SSM client inline (used only during init, not stored on the instance).
3. Call `ssm_client.get_parameters(Names=[...], WithDecryption=True)` — a single batched call.
4. Map results back to the existing attribute names.
5. Raise `ValueError` naming the missing parameter if any expected parameter is absent from the response (handles misconfiguration or permission errors early).
6. Let any other SSM API exception (network error, throttling, IAM denial) propagate unhandled — Lambda will fail the invocation and WhatsApp will retry.
7. Keep `openai_model` reading from `os.environ.get("OPENAI_MODEL", "gpt-4o-mini")`.

The existing `_get_settings()` singleton remains unchanged — SSM is called at most once per Lambda container lifetime.

---

## Known Divergence: Verify Token

`WHATSAPP_VERIFY_TOKEN_PARAM` is already handled separately in `webhook_handler.py` using `ssm.get_parameter()` (singular). This migration does not consolidate that fetch into the batched `Settings` call — it remains out of scope and is an acknowledged divergence.

---

## Testing

Existing tests in `backend/tests/config/test_settings.py` (which mock environment variables directly) will break after this change and must be replaced.

New unit tests instantiate `Settings()` directly (not via `_get_settings()`) to avoid the module-level singleton caching stale state across tests. If tests need to exercise `_get_settings()`, they must reset the singleton via a fixture (e.g. `monkeypatch.setattr("app.config.settings._settings", None)`).

Tests mock the boto3 SSM client via `unittest.mock.patch("boto3.client")` and assert:
- Correct attributes are populated from the SSM response.
- `openai_model` is read from the environment variable with the correct default.
- `ValueError` is raised when a parameter is missing from the SSM response.

No real AWS calls in tests.

---

## Out of Scope

- Rotation of SecureString parameters (manual operator responsibility).
- Consolidating the verify token fetch into `Settings`.
- Secrets Manager (Parameter Store is sufficient and cheaper at this scale).
