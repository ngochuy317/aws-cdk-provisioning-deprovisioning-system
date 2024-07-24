import os

from aws_cdk import (
    Stack,
    aws_apigateway as apigateway,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_sqs as sqs,
    aws_lambda_event_sources as lambda_event_sources,
    CfnOutput,
)
from constructs import Construct


class AwsCdkProvisioningDeprovisioningSystemStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        # self.sender_email = kwargs.pop('sender_email')
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here

        queue = sqs.Queue(self, "AwsCdkProvisioningDeprovisioningSystemQueue")

        api_gateway_role = iam.Role(
            self,
            "ApiGatewaySqsRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
        )
        api_gateway_role.add_to_policy(iam.PolicyStatement(
            actions=["sqs:SendMessage"],
            resources=[queue.queue_arn]
        ))
        # Enable logging for API Gateway
        base_api = apigateway.RestApi(
            self,
            "ProvisioningApi",
            rest_api_name="Provisioning Service",
            description="This service handles provisioning requests.",
        )
        # /contactcenter/users/{user_id}
        users_resource = (
            base_api
            .root
            .add_resource("contactcenter")
            .add_resource("users")
            .add_resource("{user_id}")
        )
        sqs_deprovisioning_integration_request_template = {
            "application/json": (
                "{"
                "\"Action\": \"SendMessage\","
                "\"MessageBody\": {\"user_id\": \"$input.params('user_id')\", \"action\": \"deprovision\"}"
                "\"QueueUrl\": \"" + queue.queue_url + "\""
                "}"
            )
        }
        # Integration with SQS
        sqs_deprovisioning_integration = apigateway.AwsIntegration(
            service="sqs",
            integration_http_method="POST",
            path="",
            action="SendMessage",
            options=apigateway.IntegrationOptions(
                credentials_role=api_gateway_role,
                # request_templates={"application/json": "Action=SendMessage&MessageBody={'user_id': $input.params('user_id')}"},
                request_templates=sqs_deprovisioning_integration_request_template,
                # request_templates={"application/x-www-form-urlencoded": "Action=SendMessage&MessageBody={'user_id': $input.params('user_id')}"},
                passthrough_behavior=apigateway.PassthroughBehavior.NEVER,
                integration_responses=[
                    apigateway.IntegrationResponse(
                        status_code="200",
                        response_templates={
                            "application/json": "{}"
                        }
                    )
                ],
                # request_parameters={"integration.request.header.Content-Type": "'application/x-www-form-urlencoded'"},
            )
        )

        # Add DELETE method to the resource with SQS integration
        users_resource.add_method(
            "DELETE",
            sqs_deprovisioning_integration,
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_models={
                        "application/json": apigateway.Model.EMPTY_MODEL
                    }
                )
            ]
        )

        # IAM Role for Lambda
        lambda_role = iam.Role(
            self,
            "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSESFullAccess")
            ]
        )

        # Attach inline policy to the role for specific SQS permissions
        lambda_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "sqs:ChangeMessageVisibility",
                "sqs:DeleteMessage",
                "sqs:GetQueueAttributes",
                "sqs:GetQueueUrl",
                "sqs:ReceiveMessage"
            ],
            resources=[queue.queue_arn]
        ))

        hello_world_function = _lambda.Function(
            self,
            "HelloWorldFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            # Points to the lambda directory
            code=_lambda.Code.from_asset("lambda"),
            # Points to the 'hello' file in the lambda directory
            handler="hello.lambda_handler",
            environment={
                "SENDER_EMAIL": os.getenv('SENDER_EMAIL')
            },
            role=lambda_role
        )

        # Add SQS Event Source to Lambda
        hello_world_function.add_event_source(lambda_event_sources.SqsEventSource(queue))

        # Outputs
        CfnOutput(self, "QueueURL", value=queue.queue_url, description="URL of the SQS Queue")
        CfnOutput(self, "QueueARN", value=queue.queue_arn, description="ARN of the SQS Queue")
        CfnOutput(
            self,
            "LambdaFunctionName",
            value=hello_world_function.function_name,
            description="Name of the Lambda function",
        )
        CfnOutput(
            self,
            "LambdaFunctionARN",
            value=hello_world_function.function_arn,
            description="ARN of the Lambda function"
        )
