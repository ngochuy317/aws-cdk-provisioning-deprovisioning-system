# Provisioning and Deprovisioning System

This project sets up and integrates AWS API Gateway, SQS, SNS, Lambda, and SSM Parameter Store using AWS CDK in Python.

## Prerequisites

Ensure you have the following installed on your machine:

- Python 3.11.9
- AWS CLI
- Node.js (for AWS CDK)
- AWS CDK

## Setup Instructions

### 1. Install Python 3.11.9

Ensure you have Python 3.11.9 installed. You can download it from the [official Python website](https://www.python.org/downloads/).

### 2. Set Up a Virtual Environment

Create and activate a virtual environment to manage your project dependencies.

```bash
python3.11 -m venv .env
source .env/bin/activate  # On Windows, use `.env\Scripts\activate`
```

### 3. Install AWS CDK

Install the AWS CDK globally using npm.

```bash
npm install -g aws-cdk
```

### 4. Install Project Dependencies

Install the required Python packages using pip.
```bash
pip install -r requirements.txt
```

### 5. Configure AWS Profile

Configure your AWS CLI with your credentials. This creates a profile that the CDK can use to deploy the stack.
```bash
aws configure --profile my-aws-profile
```

Enter the following details when prompted:

- AWS Access Key ID
- AWS Secret Access Key
- Default region name (e.g., us-east-1)
- Default output format (e.g., json)


### 6. Bootstrap Your AWS Environment

Bootstrap your AWS environment if you haven’t done so already. Ensure you use the profile you configured.

```bash
cdk bootstrap --profile my-aws-profile
```

### 7. Deploy the Stack

Deploy the stack to your AWS account using the specified profile.

```bash
cdk deploy --profile my-aws-profile
```

### 8. Clean Up

To delete the stack and all associated resources, run:

```bash
cdk destroy --profile my-aws-profile
```

Project Structure

- app.py: The entry point for the CDK application.
- provisioning_deprovisioning_system/provisioning_deprovisioning_system.py: The main stack definition.
- lambda/: Directory containing the Lambda function code.
- requirements.txt: Python dependencies for the project.
- .env.example: Example environment file.

### Environment Variables
Ensure you have a .env file in the root of your project directory. You can use the .env.example file as a template. The .env file should contain:
```plain text
SENDER_EMAIL=test@gmail.com
CDK_DEFAULT_ACCOUNT=123451
CDK_DEFAULT_REGION=us-east-1
RECIPIENT_EMAIL=custcommeng@omf.com
```