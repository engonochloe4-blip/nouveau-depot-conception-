from datetime import datetime

from models import OperationHistory, db


def login(client, username="admin", password="admin123"):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


def test_protected_route_redirects_when_not_logged_in(client):
    response = client.get("/vmware/stats")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_login_then_access_status_route(client):
    login_response = login(client)
    assert login_response.status_code == 302

    response = client.get("/vmware/status")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["simulation"] is True


def test_history_supports_filters(client, flask_app):
    login(client)

    with flask_app.app_context():
        db.session.add_all(
            [
                OperationHistory(
                    action="snapshot",
                    vm_name="VM-A",
                    status="succès",
                    message="ok",
                    created_at=datetime(2026, 5, 20, 10, 0, 0),
                ),
                OperationHistory(
                    action="restore_snapshot",
                    vm_name="VM-B",
                    status="succès",
                    message="ok",
                    created_at=datetime(2026, 5, 21, 10, 0, 0),
                ),
            ]
        )
        db.session.commit()

    response = client.get("/history?action=snapshot&vm_name=VM-A&date_from=2026-05-01&date_to=2026-05-31")

    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload["history"]) == 1
    assert payload["history"][0]["action"] == "snapshot"
    assert payload["history"][0]["vm_name"] == "VM-A"
