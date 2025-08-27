from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class ParameterSet(BaseModel):
    dataset_name: str
    data: Dict[str, Any]

class JourneyRequest(BaseModel):
    objective: str
    target_url: str
    is_live_view: bool = False
    parameters: Optional[List[ParameterSet]] = None