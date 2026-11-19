from app.services.qwen_worker import HamiWorkerRequest, HamiWorkerService


def test_hami_worker_reports_missing_local_endpoint():
    service = HamiWorkerService()
    request = HamiWorkerRequest(prompt="Audit backend schemas.")

    result = service.execute_task(request)

    assert result.success is False
    assert result.output == ""
    assert result.error == "Hami model endpoint is not configured."


def test_hami_worker_does_not_fake_success_without_an_adapter():
    service = HamiWorkerService(base_url="http://127.0.0.1:11434/v1")
    request = HamiWorkerRequest(prompt="Audit backend schemas.")

    result = service.execute_task(request)

    assert result.success is False
    assert result.output == ""
    assert result.error == "Hami worker HTTP adapter is not connected."
