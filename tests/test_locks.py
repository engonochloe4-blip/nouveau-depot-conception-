import vmware_api


def test_two_operations_on_same_vm_are_blocked(flask_app):
    vmware_api.SIMULATION_MODE = True

    with flask_app.app_context():
        first = vmware_api.acquire_vm_lock("VM-LOCK", "create_snapshot", session_id="session-a")
        second = vmware_api.acquire_vm_lock("VM-LOCK", "restore_snapshot", session_id="session-b")

        assert first["success"] is True
        assert second["success"] is False
        assert "déjà verrouillée" in second["error"]

        released = vmware_api.release_vm_lock("VM-LOCK", "session-a")
        assert released["success"] is True

        third = vmware_api.acquire_vm_lock("VM-LOCK", "restore_snapshot", session_id="session-c")
        assert third["success"] is True
