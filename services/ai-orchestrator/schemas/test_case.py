from pydantic import BaseModel, Field


class GenerationRequest(BaseModel):
    requirement: str
    target_url: str


class GenerationResponse(BaseModel):
    message: str
    test_case_id: str | None
    run_id: int | None = Field(default=None)
