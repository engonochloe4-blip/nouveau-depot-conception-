import vmware_api


def test_connect_vsphere_simulation_returns_fake_connection():
    vmware_api.SIMULATION_MODE = True

    assert vmware_api.connect_vsphere() == "simulation"


def test_list_vms_simulation_returns_sample_vm():
    vmware_api.SIMULATION_MODE = True

    vms = vmware_api.list_vms("simulation")

    assert isinstance(vms, list)
    assert len(vms) == 1
    assert vms[0]["name"] == "VM-test"
    assert vms[0]["power_state"] == "poweredOn"
    assert vms[0]["cpu"] == 2
    assert vms[0]["memory_mb"] == 4096


def test_create_snapshot_simulation_succeeds_and_clears_lock(flask_app):
    vmware_api.SIMULATION_MODE = True

    with flask_app.app_context():
        result = vmware_api.create_snapshot("VM-test", snapshot_name="snap-test", session_id="session-1")

        assert result["success"] is True
        assert result["vm_name"] == "VM-test"
        assert result["snapshot_name"] == "snap-test"

        from models import VMLock

        assert VMLock.query.filter_by(vm_name="VM-test").first() is None
