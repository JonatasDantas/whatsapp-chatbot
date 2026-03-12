import json
import boto3
import os

dynamodb = boto3.resource("dynamodb")

table = dynamodb.Table(os.environ["TABLE_NAME"])


def whatsapp_webhook(event, context):
    """
    Basic WhatsApp webhook handler.
    Currently echoes all items from the DynamoDB table as JSON.
    Extend this to parse and handle incoming WhatsApp webhook payloads.
    """
    response = table.scan()
    items = response.get("Items", [])

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
        },
        "body": json.dumps(items),
    }