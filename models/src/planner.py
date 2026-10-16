import json
from .client import complete
from .fallback import PLANNER_MODELS
from .prompts import build_planner_messages
from .schemas import TechnicalPlan, TechnicalPlanInput

def generate_technical_plan(input_data: TechnicalPlanInput) -> TechnicalPlan:
    content, _ = complete(build_planner_messages(input_data), PLANNER_MODELS, response_format={"type": "json_object"}, max_tokens=1800)
    try:
        return TechnicalPlan.model_validate(json.loads(content))
    except (json.JSONDecodeError, ValueError) as error:
        raise RuntimeError("The planning model returned an incomplete structured response. Please try again.") from error
