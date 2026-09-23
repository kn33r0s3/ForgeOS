import os
import requests
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class QwenWorkerRequest(BaseModel):
    prompt: str = Field(..., description="The prompt or task instruction for the Qwen worker.")
    system_instruction: Optional[str] = Field(None, description="Optional system role/instructions.")
    temperature: float = Field(0.2, ge=0.0, le=1.0)

class QwenWorkerResponse(BaseModel):
    success: bool
    output: str
    model: str
    error: Optional[str] = None

class QwenWorkerService:
    def __init__(self, base_url: Optional[str] = None, model_name: Optional[str] = None):
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        self.model_name = model_name or os.getenv("QWEN_MODEL_NAME", "qwen3-coder:latest")

    def execute_task(self, request: QwenWorkerRequest) -> QwenWorkerResponse:
        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"
        
        messages = []
        if request.system_instruction:
            messages.append({"role": "system", "content": request.system_instruction})
        messages.append({"role": "user", "content": request.prompt})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": request.temperature,
            "stream": False
        }

        try:
            response = requests.post(endpoint, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return QwenWorkerResponse(
                success=True,
                output=content,
                model=self.model_name
            )
        except Exception as e:
            return QwenWorkerResponse(
                success=False,
                output="",
                model=self.model_name,
                error=str(e)
            )
