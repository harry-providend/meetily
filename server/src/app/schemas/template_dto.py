from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, JsonValue

TemplateSections = dict[str, JsonValue] | list[JsonValue]


class SummaryTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    sections_json: TemplateSections
    is_builtin: bool
    user_modified: bool
    created_at: datetime
    updated_at: datetime


class SummaryTemplateListResponse(BaseModel):
    items: list[SummaryTemplateResponse]


class SummaryTemplateUpsertRequest(BaseModel):
    """is_builtin is not settable here; only seeding may declare a template builtin."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    sections_json: TemplateSections


class ShippedTemplate(BaseModel):
    """A template as it exists in the app bundle."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    sections_json: TemplateSections


class TemplateSeedRequest(BaseModel):
    templates: list[ShippedTemplate]


class TemplateSeedResponse(BaseModel):
    """Counts rather than ids: the app only logs the outcome."""

    written: int
    skipped_user_modified: int


class TemplateImportResponse(BaseModel):
    imported: list[str]
    already_present: list[str]
