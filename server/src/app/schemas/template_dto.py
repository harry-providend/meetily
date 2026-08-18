from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class SummaryTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    sections_json: dict[str, JsonValue] | list[JsonValue]
    is_builtin: bool
    user_modified: bool
    created_at: datetime
    updated_at: datetime


class SummaryTemplateListResponse(BaseModel):
    items: list[SummaryTemplateResponse]


class SummaryTemplateUpsertRequest(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    sections_json: dict[str, JsonValue] | list[JsonValue]
