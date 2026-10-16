from typing import Literal
from pydantic import BaseModel, Field, HttpUrl

class CourseRow(BaseModel):
    course_code: str = Field(min_length=1)
    course_name: str = Field(min_length=1)
    targets: list[str] = Field(min_length=1)
    official_url: HttpUrl
    overlap_count: int | None = Field(default=None, ge=1)

class TechnicalPlanInput(BaseModel):
    matrix: list[CourseRow] = Field(min_length=1)
    series_rules: list[str] = Field(default_factory=list)
    raw_notes: list[str] = Field(default_factory=list)

class TechnicalPlan(BaseModel):
    summary: str
    course_priorities: list[str]
    warnings: list[str]
    source_urls: list[HttpUrl]

class StudentSummaryInput(BaseModel):
    plan: TechnicalPlan

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)

class ChatInput(BaseModel):
    plan_context: str = Field(min_length=1)
    message: str = Field(min_length=1)
    history: list[ChatMessage] = Field(default_factory=list)

class ChatReply(BaseModel):
    reply: str
    model: str
