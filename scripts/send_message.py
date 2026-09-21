#!/usr/bin/env python3
"""
Simulate an incoming WhatsApp message by POSTing to the webhook API.

Usage:
    python scripts/send_message.py --url <API_URL> --message "Olá, quero saber sobre disponibilidade"

Options:
    --url       Webhook URL (or set WEBHOOK_URL env var)
    --message   Text message to send (default: prompts interactively)
    --phone     Sender phone number (default: +5511999990000)
    --name      Contact name (default: Cliente Teste)
"""

import argparse
import json
import os
import time
import uuid

import httpx


def build_payload(phone: str, name: str, message: str) -> dict:
    wa_id = phone.lstrip("+")
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "ENTRY_ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15550000000",
                                "phone_number_id": "PHONE_NUMBER_ID",
                            },
                            "contacts": [
                                {
                                    "profile": {"name": name},
                                    "wa_id": wa_id,
                                }
                            ],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": f"wamid.{uuid.uuid4().hex}",
                                    "timestamp": str(int(time.time())),
                                    "type": "text",
                                    "text": {"body": message},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Send a simulated WhatsApp message to the webhook.")
    parser.add_argument("--url", default="https://ubjld5ojb8.execute-api.us-east-1.amazonaws.com/prod/webhook", help="Webhook POST URL")
    parser.add_argument("--message", default=None, help="Message text")
    parser.add_argument("--phone", default="+5511999990000", help="Sender phone number")
    parser.add_argument("--name", default="Cliente Teste", help="Contact name")
    args = parser.parse_args()

    if not args.url:
        print("Error: provide --url or set WEBHOOK_URL environment variable.")
        raise SystemExit(1)

    message = args.message or input("Message: ")

    payload = build_payload(phone=args.phone, name=args.name, message=message)

    print(f"\nPOST {args.url}")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    response = httpx.post(args.url, json=payload, timeout=30)

    print(f"\nStatus: {response.status_code}")
    print(f"Body:   {response.text}")


if __name__ == "__main__":
    main()
