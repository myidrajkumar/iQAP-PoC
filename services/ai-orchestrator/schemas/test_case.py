"""Request and response schemas for test case generation."""

from pydantic import BaseModel


class GenerationRequest(BaseModel):
    """
    Defines the shape of the incoming request body for test case generation.
    """

    requirement: str
    target_url: str


class GenerationResponse(BaseModel):
    """
    Defines the shape of the response sent back to the client.
    """

    message: str
    test_case_id: str | None
