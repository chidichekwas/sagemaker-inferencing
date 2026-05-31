import os
import json
import sagemaker
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.parameters import ParameterString
from sagemaker.workflow.steps import ProcessingStep
from sagemaker.processing import ScriptProcessor, ProcessingInput, ProcessingOutput

region = "us-east-1"
role = "arn:aws:iam::148622480762:role/sagemaker-pipeline-role"
sess = sagemaker.Session()

BUCKET = "sagemaker-s3-chidi"
PROCESSED_PREFIX = "fraud/processed"
PREDICTIONS_PREFIX = "fraud/predictions"
SCRIPTS_PREFIX = "fraud/scripts"

def get_pipeline():
    input_data = ParameterString(
        name="InputData",
        default_value=f"s3://{BUCKET}/{PROCESSED_PREFIX}/",
    )

    output_s3 = ParameterString(
        name="OutputS3",
        default_value=f"s3://{BUCKET}/{PREDICTIONS_PREFIX}/",
    )

    script_processor = ScriptProcessor(
        image_uri=sagemaker.image_uris.retrieve(
            framework="sklearn",
            region=region,
            version="1.2-1",
            instance_type="ml.t3.medium",
        ),
        command=["python3"],
        role=role,
        instance_count=1,
        instance_type="ml.t3.medium",
    )

    processing_step = ProcessingStep(
        name="InvokeFraudEndpoint",
        processor=script_processor,
        inputs=[
            ProcessingInput(
                source=input_data,
                destination="/opt/ml/processing/input",
                input_name="input-data",
            )
        ],
        outputs=[
            ProcessingOutput(
                source="/opt/ml/processing/output",
                destination=output_s3,
                output_name="predictions",
            )
        ],
        code=f"s3://{BUCKET}/{SCRIPTS_PREFIX}/inference_script.py",
    )

    pipeline = Pipeline(
        name="fraud-realtime-inference-pipeline",
        parameters=[input_data, output_s3],
        steps=[processing_step],
        sagemaker_session=sess,
    )

    return pipeline

if __name__ == "__main__":
    pipeline = get_pipeline()
    pipeline.upsert(role_arn=role)
    definition = json.loads(pipeline.definition())
    with open("pipeline_definition.json", "w") as f:
        json.dump(definition, f, indent=2)
    print("Pipeline upserted and pipeline_definition.json written.")
