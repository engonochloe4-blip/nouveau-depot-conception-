from datetime import datetime
from types import SimpleNamespace

import app as app_module
import vmware_api
from models import OperationHistory, VMLock, db


def login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )


def test_app_routes_smoke(client, flask_app, monkeypatch):
    login(client)

    monkeypatch.setattr(app_module, "SIMULATION_MODE", False)
    monkeypatch.setattr(app_module, "connect_vsphere", lambda *args, **kwargs: "fake-si")
    monkeypatch.setattr(
        app_module,
        "list_vms",
        lambda service_instance: [
            {"name": "VM-A", "power_state": "poweredOn", "cpu": 2, "memory_mb": 2048},
            {"name": "VM-B", "power_state": "poweredOff", "cpu": 4, "memory_mb": 8192},
        ],
    )
    monkeypatch.setattr(
        app_module,
        "create_snapshot",
        lambda *args, **kwargs: {
            "success": True,
            "vm_name": "VM-A",
            "snapshot_name": "snap-a",
            "message": "ok",
        },
    )
    monkeypatch.setattr(
        app_module,
        "restore_snapshot",
        lambda *args, **kwargs: {
            "success": True,
            "vm_name": "VM-A",
            "snapshot_name": "snap-a",
            "message": "restored",
        },
    )
    monkeypatch.setattr(
        app_module,
        "get_vm_lock_status",
        lambda vm_name: {"locked": True, "operation": "create_snapshot", "locked_by": "session-1"},
    )

    response = client.get("/")
    assert response.status_code == 200

    response = client.get("/api/user")
    assert response.status_code == 200
    assert response.get_json()["username"] == "admin"

    response = client.get("/vmware/status")
    assert response.status_code == 200
    assert response.get_json()["connected"] is True

    response = client.get("/vmware/vms")
    payload = response.get_json()
    assert response.status_code == 200
    assert len(payload["vms"]) == 2

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
                    status="erreur",
                    message="fail",
                    created_at=datetime(2026, 5, 21, 10, 0, 0),
                ),
            ]
        )
        db.session.commit()

        lock_result = vmware_api.acquire_vm_lock("VM-A", "create_snapshot", session_id="session-1")
        assert lock_result["success"] is True

    response = client.get("/history?action=snapshot&vm_name=VM-A&date_from=2026-05-01&date_to=2026-05-31")
    assert response.status_code == 200
    assert len(response.get_json()["history"]) == 1

    response = client.post("/vmware/snapshot", json={"vm_name": "VM-A", "snapshot_name": "snap-a"})
    assert response.status_code == 200

    response = client.post("/vmware/restore-snapshot", json={"vm_name": "VM-A", "snapshot_name": "snap-a"})
    assert response.status_code == 200

    response = client.post("/vmware/restore/VM-A", json={"snapshot_name": "snap-a"})
    assert response.status_code == 200

    response = client.get("/vmware/locks")
    assert response.status_code == 200
    assert response.get_json()["locks"]

    response = client.get("/vmware/lock/VM-A")
    assert response.status_code == 200
    assert response.get_json()["locked"] is True

    response = client.post("/vmware/unlock/VM-A", json={"session_id": "session-1"})
    assert response.status_code == 200
    assert response.get_json()["success"] is True

    response = client.get("/vmware/stats")
    assert response.status_code == 200
    stats = response.get_json()
    assert stats["total_vms"] == 2
    assert stats["vms_on"] == 1
    assert stats["vms_off"] == 1

    response = client.get("/logout", follow_redirects=False)
    assert response.status_code == 302


def test_admin_required_decorator(flask_app):
    @app_module.admin_required
    def protected():
        return "ok"

    with flask_app.test_request_context("/"):
        admin = app_module.User.query.filter_by(username="admin").first()
        app_module.session["user_id"] = admin.id
        assert protected() == "ok"

    with flask_app.test_request_context("/"):
        user = app_module.User.query.filter_by(username="user").first()
        app_module.session["user_id"] = user.id
        response = protected()
        assert response[1] == 403
