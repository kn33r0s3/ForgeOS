from app.services import integration_outbox


def test_enqueue_is_idempotent_and_local(db):
    first = integration_outbox.enqueue(
        db,
        integration_name="crm",
        operation="create_contact",
        idempotency_key="contact-1",
        request={"segment": "repair shop"},
    )
    second = integration_outbox.enqueue(
        db,
        integration_name="crm",
        operation="create_contact",
        idempotency_key="contact-1",
        request={"segment": "different"},
    )

    assert first.id == second.id
    assert second.status == "QUEUED"
    assert db.query(type(first)).count() == 1


def test_failed_delivery_retries_then_fails_closed(db):
    row = integration_outbox.enqueue(
        db,
        integration_name="email",
        operation="send",
        idempotency_key="email-1",
    )
    for _ in range(integration_outbox.MAX_ATTEMPTS):
        row = integration_outbox.mark_failed(db, row.id, "provider unavailable")

    assert row.status == "FAILED"
    assert row.attempts == integration_outbox.MAX_ATTEMPTS
    assert row.next_attempt_at is None
    assert row.last_error == "provider unavailable"


def test_success_records_response_without_claiming_business_outcome(db):
    row = integration_outbox.enqueue(
        db,
        integration_name="payments",
        operation="create_checkout",
        idempotency_key="checkout-1",
    )
    row = integration_outbox.mark_succeeded(db, row.id, {"checkout_id": "vendor-1"})

    assert row.status == "SUCCEEDED"
    assert "vendor-1" in row.response_json
    assert not hasattr(row, "actual_revenue")
