import json
from pipeline import get_pipeline

def test_pipeline_builds():
    pipeline = get_pipeline()
    assert pipeline is not None

def test_pipeline_has_two_steps():
    pipeline = get_pipeline()
    step_names = [step.name for step in pipeline.steps]
    assert "FraudInferenceProcessing" in step_names
    assert "FraudPostProcessing" in step_names

def test_pipeline_parameters():
    pipeline = get_pipeline()
    params = {p.name for p in pipeline.parameters}
    assert "InputData" in params
    assert "OutputS3" in params

def test_pipeline_serializes():
    pipeline = get_pipeline()
    definition = pipeline.definition()
    parsed = json.loads(definition)
    assert "Steps" in parsed
