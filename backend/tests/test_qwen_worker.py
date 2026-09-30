import pytest
from unittest.mock import patch, MagicMock
from app.services.qwen_worker import QwenWorkerService, QwenWorkerRequest

@patch("app.services.qwen_worker.requests.post")
def test_qwen_worker_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "Refactoring plan generated successfully."
                }
            }
        ]
    }
    mock_post.return_value = mock_response

    service = QwenWorkerService(base_url="http://localhost:11434/v1", model_name="qwen2.5-coder:3b")
    request = QwenWorkerRequest(prompt="Audit backend schemas.")
    
    result = service.execute_task(request)
    
    assert result.success is True
    assert result.output == "Refactoring plan generated successfully."
    assert result.model == "qwen2.5-coder:3b"
    mock_post.assert_called_once()

@patch("app.services.qwen_worker.requests.post")
def test_qwen_worker_failure(mock_post):
    mock_post.side_effect = Exception("Connection refused")

    service = QwenWorkerService(base_url="http://localhost:11434/v1", model_name="qwen2.5-coder:3b")
    request = QwenWorkerRequest(prompt="Audit backend schemas.")
    
    result = service.execute_task(request)
    
    assert result.success is False
    assert result.output == ""
    assert "Connection refused" in result.error
