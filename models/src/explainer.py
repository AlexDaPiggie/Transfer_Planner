from .client import complete
from .fallback import EXPLAINER_MODELS
from .prompts import build_chat_messages, build_summary_messages
from .schemas import ChatInput, ChatReply, StudentSummaryInput

def generate_student_summary(input_data: StudentSummaryInput) -> str:
    content, _ = complete(build_summary_messages(input_data.plan.model_dump_json()), EXPLAINER_MODELS, max_tokens=700, temperature=0.3)
    return content

def answer_student_question(input_data: ChatInput) -> ChatReply:
    content, model = complete(build_chat_messages(input_data), EXPLAINER_MODELS, max_tokens=500, temperature=0.3)
    return ChatReply(reply=content, model=model)
