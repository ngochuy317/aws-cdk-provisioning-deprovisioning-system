import boto3
import os

ses_client = boto3.client('ses')
sns_client = boto3.client('sns')
ssm_client = boto3.client('ssm', region_name=os.environ['CDK_DEFAULT_REGION'])


def send_sns(message, subject):
    sns_client.publish(
        TopicArn=os.environ['TOPIC_ARN'],
        Message=message,
        Subject=subject,
    )


def get_parameter(name):
    response = ssm_client.get_parameter(Name=name)
    return response['Parameter']['Value']


def lambda_handler(event, context):
    for record in event['Records']:
        process_message(record)


def process_message(message):
    action = message.get("messageAttributes", {}).get("action", {}).get("stringValue")
    if action == 'provision':
        print("Provisioning resource...")
        send_sns("Provisioning Notification", "Resource has been provisioned.")
    elif action == 'deprovision':
        print("Deprovisioning resource...")
        send_sns("Deprovisioning Notification", "Resource has been deprovisioned.")
