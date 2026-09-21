# Evolution API Migration Plan

## Context

WhatsApp Cloud API (Meta) proved too bureaucratic and blocks a core requirement: keeping the personal WhatsApp account accessible on the phone. Evolution API (using the Baileys library) solves this — it connects as a WhatsApp Web "linked device", so the phone continues working normally alongside the bot.

---

## Pros & Cons of Evolution API (Baileys)

### Pros
- **Phone stays usable** — Baileys connects as a linked device (like WhatsApp Web); up to 4 devices can be linked simultaneously
- **No Meta approval** — No business verification, template approval, or account review required
- **Zero per-message cost** — No conversation-based billing like WhatsApp Cloud API
- **Faster setup** — Deploy, scan QR code, done
- **Richer message types** — Buttons, lists, stickers, polls, reactions — no template restrictions
- **Open source & self-hosted** — No vendor lock-in, full control
- **Built-in media base64** — Audio can come pre-encoded in webhook payload (`webhook_base64: true`), simplifying audio download

### Cons
- **Terms of Service risk** — Baileys reverse-engineers the WhatsApp Web protocol. Meta may ban the number, especially at scale. Low risk for a single personal use chatbot, but real risk at volume.
- **Dependent on Baileys updates** — WhatsApp app updates can break Baileys until the library catches up (usually fixed within days by the active community)
- **Self-hosted overhead** — Evolution API requires a persistent server (Docker, PostgreSQL, Redis) unlike the current purely serverless setup
- **Session re-auth** — If the server restarts without persistent storage configured, may need to re-scan QR code
- **Dual-response risk in owner takeover** — When stage is `owner_takeover`, both the owner (on phone) and the bot could theoretically respond. The existing `owner_takeover` stage guard prevents the bot from replying, so this is already handled.

---

## Architecture After Migration

```
Phone User (WhatsApp)
    ↓
Evolution API  ←→  (Baileys connects phone as linked device)
(EC2 + Docker)
    ↓ POST MESSAGES_UPSERT webhook
API Gateway
    ↓
Lambda WebhookFunction
    ↓
WebhookHandler → ProcessIncomingMessage → GenerateAIResponse
    ↓
Evolution API HTTP call  →  sends reply back to WhatsApp
```

---

## Step 1 — Add Evolution API Docker files

New directory: `infrastructure/evolution/`

### `infrastructure/evolution/Dockerfile`
Pins the Evolution API version and allows future customization:
```dockerfile
FROM atendai/evolution-api:v2.1.1
EXPOSE 8080
```

### `infrastructure/evolution/docker-compose.yml`
Orchestrates Evolution API + PostgreSQL + Redis:
```yaml
services:
  evolution-api:
    build: .
    container_name: evolution_api
    restart: always
    ports:
      - "8080:8080"
    env_file:
      - .env
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:15-alpine
    container_name: evolution_postgres
    restart: always
    environment:
      POSTGRES_USER: evolution
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: evolution
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    container_name: evolution_redis
    restart: always
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

### `infrastructure/evolution/nginx.conf`
Reverse proxy with SSL termination (Certbot fills in certificate paths):
```nginx
server {
    listen 80;
    server_name evolution.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name evolution.yourdomain.com;

    # Certbot will add certificate directives here

    location / {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

---

## Step 2 — Create `EvolutionStack` in CDK

**New file:** `infrastructure/cdk/stacks/evolution_stack.py`

Provisions: EC2 t2.micro (free tier), Security Group, Elastic IP, IAM role, and UserData that installs Docker, copies the docker-compose files, fetches secrets from SSM, and starts services.

```python
from aws_cdk import Stack, CfnOutput
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from constructs import Construct

class EvolutionStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        vpc = ec2.Vpc.from_lookup(self, "DefaultVpc", is_default=True)

        sg = ec2.SecurityGroup(self, "EvolutionSg", vpc=vpc, description="Evolution API")
        sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "HTTP")
        sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443), "HTTPS")
        sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(22), "SSH")

        role = iam.Role(self, "EvolutionRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"))
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"))
        role.add_to_policy(iam.PolicyStatement(
            actions=["ssm:GetParameter"],
            resources=[
                f"arn:aws:ssm:{self.region}:{self.account}:parameter/chacara-chatbot/evolution-api-key",
                f"arn:aws:ssm:{self.region}:{self.account}:parameter/chacara-chatbot/evolution-postgres-password",
            ]))
        role.add_to_policy(iam.PolicyStatement(
            actions=["kms:Decrypt"],
            resources=[f"arn:aws:kms:{self.region}:{self.account}:alias/aws/ssm"]))

        ubuntu_ami = ec2.MachineImage.lookup(
            name="ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*",
            owners=["099720109477"])  # Canonical

        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            "apt-get update -y",
            "apt-get install -y docker.io docker-compose-plugin awscli nginx certbot python3-certbot-nginx",
            "systemctl enable docker && systemctl start docker",
            "mkdir -p /opt/evolution",
            # Copy docker-compose files (uploaded to instance via CDK asset or inline)
            "REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)",
            "EVOLUTION_KEY=$(aws ssm get-parameter --name /chacara-chatbot/evolution-api-key --with-decryption --query Parameter.Value --output text --region $REGION)",
            "POSTGRES_PASS=$(aws ssm get-parameter --name /chacara-chatbot/evolution-postgres-password --with-decryption --query Parameter.Value --output text --region $REGION)",
            # Write .env for docker-compose
            "cat > /opt/evolution/.env << EOF",
            "SERVER_URL=https://evolution.yourdomain.com",
            "AUTHENTICATION_API_KEY=$EVOLUTION_KEY",
            "DATABASE_PROVIDER=postgresql",
            "DATABASE_CONNECTION_URI=postgresql://evolution:$POSTGRES_PASS@postgres:5432/evolution",
            "CACHE_REDIS_URI=redis://redis:6379",
            "CACHE_REDIS_ENABLED=true",
            "DATABASE_SAVE_DATA_NEW_MESSAGE=true",
            "EOF",
            "cd /opt/evolution && docker compose up -d",
        )

        instance = ec2.Instance(self, "EvolutionInstance",
            instance_type=ec2.InstanceType("t2.micro"),
            machine_image=ubuntu_ami,
            vpc=vpc,
            security_group=sg,
            role=role,
            user_data=user_data,
            key_name="chacara-evolution-key")  # Pre-create this key pair in EC2 console

        eip = ec2.CfnEIP(self, "EvolutionEip", instance_id=instance.instance_id)
        CfnOutput(self, "EvolutionPublicIp", value=eip.ref)
```

**Update `infrastructure/app.py`** to register the new stack:
```python
from cdk.stacks.evolution_stack import EvolutionStack
evolution = EvolutionStack(app, "ChacaraEvolutionStack")
```

**Pre-deploy requirements (manual, one-time):**
- Create an EC2 key pair named `chacara-evolution-key` in the AWS console (download the `.pem`)
- Create SSM SecureString parameters:
  - `/chacara-chatbot/evolution-api-key` — strong random string
  - `/chacara-chatbot/evolution-postgres-password` — strong random string

### Post-deploy setup (one-time, after `cdk deploy ChacaraEvolutionStack`)
1. SSH into the instance, run Certbot: `sudo certbot --nginx -d evolution.yourdomain.com`
2. Copy `nginx.conf` to `/etc/nginx/sites-available/evolution` and reload Nginx
3. Create WhatsApp instance and scan QR code:
   ```
   POST https://evolution.yourdomain.com/instance/create
   Headers: { apikey: <your-key> }
   Body: { "instanceName": "chacara", "integration": "WHATSAPP-BAILEYS", "qrcode": true }
   ```
4. Configure webhook pointing to API Gateway:
   ```json
   POST /webhook/set/chacara
   {
     "url": "https://<api-gateway-url>/webhook",
     "webhook_by_events": false,
     "webhook_base64": true,
     "events": ["MESSAGES_UPSERT"]
   }
   ```
   `webhook_base64: true` delivers audio as base64 directly in the payload — no separate download call needed.

---

## Step 3 — Update SSM Parameters

**File:** `infrastructure/cdk/stacks/backend_stack.py`

Remove old parameters:
- `/chacara-chatbot/whatsapp-verify-token`
- `/chacara-chatbot/whatsapp-access-token`
- `/chacara-chatbot/whatsapp-phone-number-id`

Add new parameters (create manually in SSM, reference in CDK):
- `/chacara-chatbot/evolution-api-url` — base URL of the EC2 instance (e.g. `https://evolution.yourdomain.com`)
- `/chacara-chatbot/evolution-api-key` — same key used in the EC2 `.env`
- `/chacara-chatbot/evolution-instance-name` — instance name used during creation (e.g. `chacara`)

Update Lambda env vars in CDK to reference new parameter names.

---

## Step 4 — Update `settings.py`

**File:** `backend/app/config/settings.py`

Remove:
```python
whatsapp_access_token: str
whatsapp_phone_number_id: str
whatsapp_verify_token: str
```

Add:
```python
evolution_api_url: str
evolution_api_key: str
evolution_instance_name: str
```

Update `_get_settings()` to load from new SSM parameter names.

---

## Step 5 — Rewrite `whatsapp_client.py`


**File:** `backend/app/integrations/whatsapp/whatsapp_client.py`

| Old (Cloud API) | New (Evolution API) |
|---|---|
| `POST https://graph.facebook.com/v19.0/{phone_id}/messages` | `POST {evolution_url}/message/sendText/{instance}` |
| `Authorization: Bearer {token}` header | `apikey: {api_key}` header |
| `GET /v19.0/{media_id}` → get URL | No longer needed (`webhook_base64: true`) |
| `GET CDN_URL` with auth → bytes | `base64.b64decode(webhook_data)` instead |

New `send_text(to, text)`:
```python
POST {EVOLUTION_URL}/message/sendText/{INSTANCE}
Headers: { apikey: API_KEY }
Body: { "number": to, "text": text }
```

New audio handling: audio bytes arrive directly as base64 in the webhook, decoded in `message_parser.py`. `WhatsAppClient` no longer needs media download methods.

---

## Step 6 — Rewrite `message_parser.py`

**File:** `backend/app/integrations/whatsapp/message_parser.py`

### New Webhook Payload (Evolution API `MESSAGES_UPSERT`)
```json
{
  "event": "messages.upsert",
  "instance": "my-instance",
  "data": {
    "key": {
      "remoteJid": "5511999999999@s.whatsapp.net",
      "fromMe": false,
      "id": "ABC123"
    },
    "pushName": "Contact Name",
    "message": {
      "conversation": "text content here"
    },
    "messageType": "conversation",
    "messageTimestamp": 1710280800
  }
}
```

For audio (with `webhook_base64: true`):
```json
{
  "data": {
    "message": {
      "base64": "<base64-encoded-audio-bytes>"
    },
    "messageType": "audioMessage"
  }
}
```

Parser logic:
1. Check `event == "messages.upsert"` — skip anything else
2. Check `data.key.fromMe == false` — skip self-sent messages
3. Extract phone from `remoteJid` by stripping `@s.whatsapp.net`
4. `messageType == "conversation"` → text message, content from `message.conversation`
5. `messageType == "audioMessage"` → audio, bytes from `base64.b64decode(message.base64)`
6. Other types → log warning, skip

---

## Step 7 — Update `webhook_handler.py`

**File:** `backend/app/handlers/webhook_handler.py`

- **Remove** the GET verification handler (`_handle_verification`) — Evolution API has no hub.challenge flow
- In `_handle_incoming()`: check `payload.get("event") == "messages.upsert"` before processing; return 200 silently for any other event (connection updates, QR code events, etc.)
- The POST structure is otherwise the same: parse → process → respond

---

## Step 8 — Update Tests

**Files:**
- `backend/tests/handlers/test_webhook_handler.py`
- `backend/tests/integrations/whatsapp/test_whatsapp_client.py`
- `backend/tests/e2e/test_webhook_flow.py`

Update all fixture payloads to Evolution API format. Remove verification GET tests. Add `fromMe: true` skip test. Add `event != "messages.upsert"` skip test.

---

## Verification

1. Deploy Evolution API on EC2, connect phone, verify QR scan works
2. Send a WhatsApp message to the connected number from another phone
3. Confirm the webhook POST arrives at API Gateway (check CloudWatch logs)
4. Confirm the Lambda parses the message correctly
5. Confirm a reply is sent back via Evolution API → appears on the original phone
6. Send a voice note → confirm Whisper transcription works end-to-end
7. Run `pytest backend/tests/` — all tests green
