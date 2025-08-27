from pydantic import BaseModel


class GenerationRequest(BaseModel):
    requirement: str
    target_url: str


class GenerationResponse(BaseModel):
    message: str
    test_case_id: str | None
