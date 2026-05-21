from types import SimpleNamespace

import vmware_api


def test_connect_vsphere_real_path_uses_smartconnect(monkeypatch):
    calls = {}

    def fake_smartconnect(**kwargs):
        calls.update(kwargs)
        return "real-connection"

    monkeypatch.setattr(vmware_api, "SIMULATION_MODE", False)
    monkeypatch.setattr(vmware_api, "SmartConnect", fake_smartconnect)

    connection = vmware_api.connect_vsphere("vcsa.local", "user", "pass", 443)

    assert connection == "real-connection"
    assert calls["host"] == "vcsa.local"
    assert calls["user"] == "user"


def test_list_vms_real_path_returns_vm_details(monkeypatch):
    vmware_api.SIMULATION_MODE = False

    fake_vm_1 = SimpleNamespace(
        name="VM-1",
        runtime=SimpleNamespace(powerState="poweredOn"),
        config=SimpleNamespace(hardware=SimpleNamespace(numCPU=2, memoryMB=4096)),
    )
    fake_vm_2 = SimpleNamespace(
        name="VM-2",
        runtime=SimpleNamespace(powerState="poweredOff"),
        config=SimpleNamespace(hardware=SimpleNamespace(numCPU=4, memoryMB=8192)),
    )

    fake_container = SimpleNamespace(view=[fake_vm_1, fake_vm_2], Destroy=lambda: None)
    fake_content = SimpleNamespace(
        viewManager=SimpleNamespace(CreateContainerView=lambda *args, **kwargs: fake_container),
        rootFolder=object(),
    )
    fake_service_instance = SimpleNamespace(RetrieveContent=lambda: fake_content)

    vms = vmware_api.list_vms(fake_service_instance)

    assert vms == [
        {"name": "VM-1", "power_state": "poweredOn", "cpu": 2, "memory_mb": 4096},
        {"name": "VM-2", "power_state": "poweredOff", "cpu": 4, "memory_mb": 8192},
    ]


def test_create_snapshot_real_path(monkeypatch, flask_app):
    vmware_api.SIMULATION_MODE = False

    class FakeTaskInfo:
        state = "success"
        error = None

    class FakeTask:
        info = FakeTaskInfo()

    class FakeVM:
        name = "VM-REAL"

        def CreateSnapshot_Task(self, **kwargs):
            return FakeTask()

    fake_container = SimpleNamespace(view=[FakeVM()], Destroy=lambda: None)
    fake_content = SimpleNamespace(
        viewManager=SimpleNamespace(CreateContainerView=lambda *args, **kwargs: fake_container),
        rootFolder=object(),
    )
    fake_service_instance = SimpleNamespace(RetrieveContent=lambda: fake_content)

    with flask_app.app_context():
        result = vmware_api.create_snapshot("VM-REAL", snapshot_name="snap-real", service_instance=fake_service_instance, session_id="session-9")

    assert result["success"] is True
    assert result["snapshot_name"] == "snap-real"


def test_restore_snapshot_real_path(monkeypatch, flask_app):
    vmware_api.SIMULATION_MODE = False

    class FakeTaskInfo:
        state = "success"
        error = None

    class FakeTask:
        info = FakeTaskInfo()

    class FakeSnapshot:
        def RevertToSnapshot_Task(self):
            return FakeTask()

    class FakeVM:
        name = "VM-REAL"
        snapshot = SimpleNamespace(
            rootSnapshotList=[SimpleNamespace(name="snap-real", snapshot=FakeSnapshot())]
        )

    fake_container = SimpleNamespace(view=[FakeVM()], Destroy=lambda: None)
    fake_content = SimpleNamespace(
        viewManager=SimpleNamespace(CreateContainerView=lambda *args, **kwargs: fake_container),
        rootFolder=object(),
    )
    fake_service_instance = SimpleNamespace(RetrieveContent=lambda: fake_content)

    with flask_app.app_context():
        result = vmware_api.restore_snapshot("VM-REAL", "snap-real", service_instance=fake_service_instance, session_id="session-10")

    assert result["success"] is True
    assert result["snapshot_name"] == "snap-real"
