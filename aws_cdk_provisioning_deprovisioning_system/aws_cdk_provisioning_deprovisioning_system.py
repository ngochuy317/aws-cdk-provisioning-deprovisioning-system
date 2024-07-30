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
        self.provisioning_queue = self.create_sqs_queue("ProvisioningSystemQueue")
        self.deprovisioning_queue = self.create_sqs_queue("DeprovisioningSystemQueue")

        self.api_gateway_role = self.create_api_gateway_role()

        self.api_gw = self.create_api_gateway()

        self.create_api_resources_and_methods()

        self.ssm_parameter = self.create_ssm_parameter()

        self.transaction_topic = self.create_topic_sns()

        self.lambda_role = self.create_lambda_role()

        self.provisioning_lambda_function = self.create_lambda_function(
            "ProvisioningLambdaFunction",
            "provisioning_lambda.lambda_handler",
            self.lambda_role,
        )
        self.provisioning_lambda_function.add_event_source(
            lambda_event_sources.SqsEventSource(self.provisioning_queue)
        )

        self.deprovisioning_lambda_function = self.create_lambda_function(
            "DeprovisioningLambdaFunction",
            "deprovisioning_lambda.lambda_handler",
            self.lambda_role,
        )
        self.deprovisioning_lambda_function.add_event_source(
            lambda_event_sources.SqsEventSource(self.deprovisioning_queue)
        )

        self.create_outputs()

    def create_sqs_queue(self, queue_name: str) -> sqs.Queue:
        return sqs.Queue(self, queue_name, content_based_deduplication=True, fifo=True)

    def create_api_gateway_role(self) -> iam.Role:
        role = iam.Role(
            self,
            "ApiGatewaySqsRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
        )
        role.add_to_policy(iam.PolicyStatement(
            actions=["sqs:SendMessage", "sqs:ReceiveMessage"],
            resources=[self.provisioning_queue.queue_arn, self.deprovisioning_queue.queue_arn]
        ))
        return role

    def create_api_gateway(self) -> apigateway.RestApi:
        return apigateway.RestApi(
            self,
            "ProvisioningApi",
            rest_api_name="Provisioning Service",
            description="This service handles provisioning requests.",
        )

    def create_api_resources_and_methods(self) -> None:

        contactcenter_resource = self.api_gw.root.add_resource("contactcenter")
        user_resource = contactcenter_resource.add_resource("{user_id}")

        deprovisioning_integration_request_template = {
            "application/json": (
                "Action=SendMessage&"
                "MessageBody=$input.body&"
                "MessageGroupId=111&"
                "MessageDeduplicationId=abc&"
                "MessageAttribute.1.Name=userID&"
                "MessageAttribute.1.Value.StringValue=$input.params('user_id')&"
                "MessageAttribute.1.Value.DataType=Number"
            )
        }

        deprovisioning_integration = apigateway.AwsIntegration(
            service="sqs",
            integration_http_method="POST",
            path=f"{os.getenv('CDK_DEFAULT_ACCOUNT')}/{self.deprovisioning_queue.queue_name}",
            options=apigateway.IntegrationOptions(
                credentials_role=self.api_gateway_role,
                request_templates=deprovisioning_integration_request_template,
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

        provisioning_integration_request_template = {
            "application/json": (
                "Action=SendMessage&"
                "MessageBody=$input.body&"
                "MessageGroupId=234&"
                "MessageDeduplicationId=abb&"
                "MessageAttribute.1.Name=userID&"
                "MessageAttribute.1.Value.StringValue=$input.params('user_id')&"
                "MessageAttribute.1.Value.DataType=Number"
            )
        }

        provisioning_integration = apigateway.AwsIntegration(
            service="sqs",
            integration_http_method="POST",
            path=f"{os.getenv('CDK_DEFAULT_ACCOUNT')}/{self.provisioning_queue.queue_name}",
            options=apigateway.IntegrationOptions(
                credentials_role=self.api_gateway_role,
                request_templates=provisioning_integration_request_template,
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
            deprovisioning_integration,
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

        user_resource.add_method(
            "PUT",
            provisioning_integration,
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
            sns_subs.EmailSubscription(os.environ['RECIPIENT_EMAIL'])
        )
        return transaction_topic

    def create_lambda_role(self) -> iam.Role:
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
            resources=[self.provisioning_queue.queue_arn, self.deprovisioning_queue.queue_arn]
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
        return lambda_role

    def create_lambda_function(self, lambda_function_name: str, handler: str, role: iam.Role) -> _lambda.Function:

        lambda_function = _lambda.Function(
            self,
            lambda_function_name,
            runtime=_lambda.Runtime.PYTHON_3_11,
            # Points to the lambda directory
            code=_lambda.Code.from_asset("lambda"),
            # Points to the 'hello' file in the lambda directory
            handler=handler,
            environment={
                "SENDER_EMAIL": os.getenv('SENDER_EMAIL'),
                "CDK_DEFAULT_REGION": os.getenv('CDK_DEFAULT_REGION'),
                "TOPIC_ARN": self.transaction_topic.topic_arn
            },
            role=role
        )

        return lambda_function

    def create_outputs(self) -> None:
        CfnOutput(
            self,
            "ProvisioningQueueURL",
            value=self.provisioning_queue.queue_url,
            description="URL of the SQS Provisioning Queue"
        )
        CfnOutput(
            self,
            "ProvisioningQueueARN",
            value=self.provisioning_queue.queue_arn,
            description="ARN of the Provisioning SQS Queue"
        )
        CfnOutput(
            self,
            "DeprovisioningQueueURL",
            value=self.deprovisioning_queue.queue_url,
            description="URL of the SQS Deprovisioning Queue"
        )
        CfnOutput(
            self,
            "DeprovisioningQueueARN",
            value=self.deprovisioning_queue.queue_arn,
            description="ARN of the Deprovisioning SQS Queue"
        )
        CfnOutput(
            self,
            "ProvisioningLambdaFunctionName",
            value=self.provisioning_lambda_function.function_name,
            description="Name of the Provisioning Lambda function",
        )
        CfnOutput(
            self,
            "ProvisioningLambdaFunctionARN",
            value=self.provisioning_lambda_function.function_arn,
            description="ARN of the provisioning Lambda function"
        )
        CfnOutput(
            self,
            "DeprovisioningLambdaFunctionName",
            value=self.deprovisioning_lambda_function.function_name,
            description="Name of the Deprovisioning Lambda function",
        )
        CfnOutput(
            self,
            "DeprovisioningLambdaFunctionARN",
            value=self.deprovisioning_lambda_function.function_arn,
            description="ARN of the Deprovisioning Lambda function"
        )
        CfnOutput(
            self,
            "TransactionSNSTopicARN",
            value=self.transaction_topic.topic_arn,
            description="ARN of the transaction Topic"
        )
