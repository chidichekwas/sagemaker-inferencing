import boto3

def handler(event, context):
    glue = boto3.client("glue")
    glue.start_job_run(JobName="fraud-etl-job")
    return {"status": "started"}
