import boto3
import os
from botocore.exceptions import ClientError

ses_client = boto3.client('ses')
ssm_client = boto3.client('ssm', region_name=os.environ['CDK_DEFAULT_REGION'])


def get_parameter(name):
    response = ssm_client.get_parameter(Name=name)
    return response['Parameter']['Value']


def lambda_handler(event, context):
    for record in event['Records']:
        process_message(record)


def send_email(subject, body_text):
    recipient_email = get_parameter("/config/recipient_email")
    body_html = f"<html><body><h1>{subject}</h1><p>{body_text}</p></body></html>"
    try:
        response = ses_client.send_email(
            Destination={
                'ToAddresses': [recipient_email],
            },
            Message={
                'Body': {
                    'Html': {
                        'Charset': "UTF-8",
                        'Data': body_html,
                    },
                    'Text': {
                        'Charset': "UTF-8",
                        'Data': body_text,
                    },
                },
                'Subject': {
                    'Charset': "UTF-8",
                    'Data': subject,
                },
            },
            Source=os.environ['SENDER_EMAIL'],
        )
    except ClientError as e:
        print(f"Error sending email: {e.response['Error']['Message']}")
    else:
        print(f"Email sent! Message ID: {response['MessageId']}")


def process_message(message):
    action = message.get("messageAttributes", {}).get("action", {}).get("stringValue")
    if action == 'provision':
        print("Provisioning resource...")
        send_email("Provisioning Notification", "Resource has been provisioned.")
    elif action == 'deprovision':
        print("Deprovisioning resource...")
        send_email("Deprovisioning Notification", "Resource has been deprovisioned.")
