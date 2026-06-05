import json
import sagemaker
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.parameters import ParameterString
from sagemaker.workflow.steps import ProcessingStep
from sagemaker.processing import ScriptProcessor, ProcessingInput, ProcessingOutput

# -------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------

region = "us-east-1"
role = "arn:aws:iam::148622480762:role/fraud-sagemaker-pipeline-role"

sess = sagemaker.Session()

BUCKET = "sagemaker-s3-chidi"
PROCESSED_PREFIX = "fraud/processed"
PREDICTIONS_PREFIX = "fraud/predictions"
LOGS_PREFIX = "fraud/logs"
POSTPROCESSED_PREFIX = "fraud/postprocessed"

INFERENCE_SCRIPT_S3_PATH = f"s3://{BUCKET}/fraud/scripts/inference_script_v2.py"
POSTPROCESS_SCRIPT_S3_PATH = f"s3://{BUCKET}/fraud/scripts/postprocess.py"


# -------------------------------------------------------------------
# PIPELINE DEFINITION
# -------------------------------------------------------------------

def get_pipeline():

    input_data = ParameterString(
        name="InputData",
        default_value=f"s3://{BUCKET}/{PROCESSED_PREFIX}/",
    )

    output_s3 = ParameterString(
        name="OutputS3",
        default_value=f"s3://{BUCKET}/{PREDICTIONS_PREFIX}/",
    )

    # -----------------------------
    # STEP 1 — INFERENCE
    # -----------------------------
    inference_processor = ScriptProcessor(
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

    inference_step = ProcessingStep(
        name="FraudInferenceProcessing",
        processor=inference_processor,
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
            ),
            ProcessingOutput(
                source="/opt/ml/processing/logs",
                destination=f"s3://{BUCKET}/{LOGS_PREFIX}/",
                output_name="logs",
            ),
        ],
        code=INFERENCE_SCRIPT_S3_PATH,
    )

    # -----------------------------
    # STEP 2 — POST‑PROCESSING
    # -----------------------------
    post_processor = ScriptProcessor(
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

    postprocess_step = ProcessingStep(
        name="FraudPostProcessing",
        processor=post_processor,
        inputs=[
            ProcessingInput(
                source=inference_step.properties.ProcessingOutputConfig
                .Outputs["predictions"].S3Output.S3Uri,
                destination="/opt/ml/processing/input",
                input_name="predictions-input",
            )
        ],
        outputs=[
            ProcessingOutput(
                source="/opt/ml/processing/output",
                destination=f"s3://{BUCKET}/{POSTPROCESSED_PREFIX}/",
                output_name="postprocessed",
            )
        ],
        code=POSTPROCESS_SCRIPT_S3_PATH,
    )

    pipeline = Pipeline(
        name="fraud-realtime-inference-pipeline",
        parameters=[input_data, output_s3],
        steps=[inference_step, postprocess_step],
        sagemaker_session=sess,
    )

    return pipeline


# -------------------------------------------------------------------
# PIPELINE DEPLOYMENT + EXECUTION
# -------------------------------------------------------------------

if __name__ == "__main__":
    pipeline = get_pipeline()

    pipeline.upsert(role_arn=role)
    print("Pipeline successfully upserted.")

    definition = json.loads(pipeline.definition())
    with open("pipeline_definition.json", "w") as f:
        json.dump(definition, f, indent=2)

    execution = pipeline.start()
    print("Pipeline execution started:", execution.arn)
