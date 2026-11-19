from typing import Optional

from pydantic import BaseModel, Field


class HamiWorkerRequest(BaseModel):
    prompt: str = Field(..., description="The prompt or task instruction for Hami.")
    system_instruction: Optional[str] = Field(None, description="Optional system role/instructions.")
    temperature: float = Field(0.2, ge=0.0, le=1.0)


class HamiWorkerResponse(BaseModel):
    success: bool
    output: str
    model: str = "hami-model"
    error: Optional[str] = None


class HamiWorkerService:
    def __init__(self, base_url: Optional[str] = None, model_name: Optional[str] = None):
        self.base_url = (base_url or "").strip().rstrip("/")
        self.model_name = model_name or "hami-model"

    def execute_task(self, request: HamiWorkerRequest) -> HamiWorkerResponse:
        if not self.base_url:
            return HamiWorkerResponse(
                success=False,
                output="",
                model="hami-model",
                error="Hami model endpoint is not configured.",
            )
        return HamiWorkerResponse(
            success=False,
            output="",
            model="hami-model",
            error="Hami worker HTTP adapter is not connected.",
        )
