import os

from aws_cdk import (
    Stack,
    aws_apigateway as apigateway,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_sns as sns,
    aws_sns_subscriptions as sns_subs,
    aws_sqs as sqs,
    aws_lambda_event_sources as lambda_event_sources,
    aws_ssm as ssm,
    CfnOutput,
)
from constructs import Construct


class AwsCdkProvisioningDeprovisioningSystem(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here
        self.queue = self.create_sqs_queue()

        self.api_gateway_role = self.create_api_gateway_role()

        self.api_gw = self.create_api_gateway()

        self.create_api_resources_and_methods()

        self.ssm_parameter = self.create_ssm_parameter()

        self.transaction_topic = self.create_topic_sns()

        self.hello_world_function = self.create_lambda_function()

        self.create_outputs()

    def create_sqs_queue(self) -> sqs.Queue:
        return sqs.Queue(self, "AwsCdkProvisioningDeprovisioningSystemQueue")

    def create_api_gateway_role(self) -> iam.Role:
        role = iam.Role(
            self,
            "ApiGatewaySqsRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
        )
        role.add_to_policy(iam.PolicyStatement(
            actions=["sqs:SendMessage", "sqs:ReceiveMessage"],
            resources=[self.queue.queue_arn]
        ))
        return role

    def create_api_gateway(self) -> apigateway.RestApi:
        return apigateway.RestApi(
            self,
            "ProvisioningApi",
            rest_api_name="Provisioning Service",
            description="This service handles provisioning requests.",
        )

    def create_api_resources_and_methods(self):

        contactcenter_resource = self.api_gw.root.add_resource("contactcenter")
        users_resource = contactcenter_resource.add_resource("users")
        user_resource = contactcenter_resource.add_resource("{user_id}")

        delete_user_integration_request_template = {
            "application/json": (
                "Action=SendMessage&"
                "MessageBody=$input.body&"
                "MessageAttribute.1.Name=userID&"
                "MessageAttribute.1.Value.StringValue=$input.params('user_id')&"
                "MessageAttribute.1.Value.DataType=Number&"
                "MessageAttribute.2.Name=action&"
                "MessageAttribute.2.Value.StringValue=deprovision&"
                "MessageAttribute.2.Value.DataType=String"
            )
        }

        delete_user_integration = apigateway.AwsIntegration(
            service="sqs",
            integration_http_method="POST",
            path=f"{os.getenv('CDK_DEFAULT_ACCOUNT')}/{self.queue.queue_name}",
            options=apigateway.IntegrationOptions(
                credentials_role=self.api_gateway_role,
                request_templates=delete_user_integration_request_template,
                integration_responses=[
                    apigateway.IntegrationResponse(
                        status_code="200",
                        response_templates={
                            "application/json": "{}"
                        }
                    )
                ],
                request_parameters={"integration.request.header.Content-Type": "'application/x-www-form-urlencoded'"},
            )
        )

        create_user_integration_request_template = {
            "application/json": (
                "Action=SendMessage&"
                "MessageBody=$input.body&"
                "MessageAttribute.1.Name=action&"
                "MessageAttribute.1.Value.StringValue=provision&"
                "MessageAttribute.1.Value.DataType=String"
            )
        }

        create_user_integration = apigateway.AwsIntegration(
            service="sqs",
            integration_http_method="POST",
            path=f"{os.getenv('CDK_DEFAULT_ACCOUNT')}/{self.queue.queue_name}",
            options=apigateway.IntegrationOptions(
                credentials_role=self.api_gateway_role,
                request_templates=create_user_integration_request_template,
                integration_responses=[
                    apigateway.IntegrationResponse(
                        status_code="200",
                        response_templates={
                            "application/json": "{}"
                        }
                    )
                ],
                request_parameters={"integration.request.header.Content-Type": "'application/x-www-form-urlencoded'"},
            )
        )

        user_resource.add_method(
            "DELETE",
            delete_user_integration,
            authorization_type=apigateway.AuthorizationType.IAM,
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_models={
                        "application/json": apigateway.Model.EMPTY_MODEL
                    }
                )
            ]
        )

        users_resource.add_method(
            "POST",
            create_user_integration,
            authorization_type=apigateway.AuthorizationType.IAM,
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_models={
                        "application/json": apigateway.Model.EMPTY_MODEL
                    }
                )
            ]
        )

    def create_ssm_parameter(self) -> ssm.StringParameter:
        return ssm.StringParameter(
            self,
            "ConfigParameter",
            parameter_name="/config/recipient_email",
            string_value="randomvalue"
        )

    def create_topic_sns(self) -> sns.Topic:
        transaction_topic = sns.Topic(
            self,
            id="sns_transaction_topic_id"
        )
        transaction_topic.add_subscription(
            sns_subs.EmailSubscription("ngochuy317@gmail.com")
        )
        return transaction_topic

    def create_lambda_function(self) -> _lambda.Function:
        lambda_role = iam.Role(
            self,
            "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ]
        )
        lambda_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "sqs:ChangeMessageVisibility",
                "sqs:DeleteMessage",
                "sqs:GetQueueAttributes",
                "sqs:GetQueueUrl",
                "sqs:ReceiveMessage",
            ],
            resources=[self.queue.queue_arn]
        ))
        lambda_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "ssm:GetParameter",
            ],
            resources=["*"]
        ))
        lambda_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "sns:publish"
            ],
            resources=[self.transaction_topic.topic_arn]
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
                "SENDER_EMAIL": os.getenv('SENDER_EMAIL'),
                "CDK_DEFAULT_REGION": os.getenv('CDK_DEFAULT_REGION'),
                "TOPIC_ARN": self.transaction_topic.topic_arn
            },
            role=lambda_role
        )

        hello_world_function.add_event_source(lambda_event_sources.SqsEventSource(self.queue))
        return hello_world_function

    def create_outputs(self) -> None:
        CfnOutput(self, "QueueURL", value=self.queue.queue_url, description="URL of the SQS Queue")
        CfnOutput(self, "QueueARN", value=self.queue.queue_arn, description="ARN of the SQS Queue")
        CfnOutput(
            self,
            "LambdaFunctionName",
            value=self.hello_world_function.function_name,
            description="Name of the Lambda function",
        )
        CfnOutput(
            self,
            "LambdaFunctionARN",
            value=self.hello_world_function.function_arn,
            description="ARN of the Lambda function"
        )
        CfnOutput(
            self,
            "TransactionSNSTopicARN",
            value=self.transaction_topic.topic_arn,
            description="ARN of the transaction Topic"
        )
