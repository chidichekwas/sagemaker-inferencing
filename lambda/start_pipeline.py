import boto3
import os

PIPELINE_NAME = os.environ["PIPELINE_NAME"]

sm = boto3.client("sagemaker")

def lambda_handler(event, context):
    resp = sm.start_pipeline_execution(PipelineName=PIPELINE_NAME)
    return {"pipelineExecutionArn": resp["PipelineExecutionArn"]}
