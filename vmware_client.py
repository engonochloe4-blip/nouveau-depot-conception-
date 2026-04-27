import os
import socket
import ssl

from pyVim.connect import Disconnect, SmartConnect
from pyVmomi import vim

SIMULATION_MODE = os.getenv("SIMULATION_MODE", "1") == "1"
VCENTER_HOST = os.getenv("VCENTER_HOST", "IP_OU_HOST_VMWARE")
VCENTER_USERNAME = os.getenv("VCENTER_USERNAME", "ton_user")
VCENTER_PASSWORD = os.getenv("VCENTER_PASSWORD", "ton_password")
VCENTER_PORT = int(os.getenv("VCENTER_PORT", "443"))


def _require_real_config():
    if not VCENTER_HOST or VCENTER_HOST == "IP_OU_HOST_VMWARE":
        raise RuntimeError("VCENTER_HOST n'est pas defini. Configure une IP ou un nom DNS valide.")
    if not VCENTER_USERNAME or VCENTER_USERNAME == "ton_user":
        raise RuntimeError("VCENTER_USERNAME n'est pas defini.")
    if not VCENTER_PASSWORD or VCENTER_PASSWORD == "ton_password":
        raise RuntimeError("VCENTER_PASSWORD n'est pas defini.")


def connect_vsphere():
    if SIMULATION_MODE:
        return "fake_connection"

    _require_real_config()

    context = ssl._create_unverified_context()
    try:
        return SmartConnect(
            host=VCENTER_HOST,
            user=VCENTER_USERNAME,
            pwd=VCENTER_PASSWORD,
            port=VCENTER_PORT,
            sslContext=context,
        )
    except socket.gaierror as exc:
        raise RuntimeError(
            f"Impossible de resoudre '{VCENTER_HOST}'. "
            "Remplace VCENTER_HOST par une IP ou un nom DNS valide."
        ) from exc


def disconnect_vsphere(service_instance):
    if service_instance is not None and not SIMULATION_MODE:
        Disconnect(service_instance)


def list_vms(service_instance=None):
    if SIMULATION_MODE:
        return ["test-ubuntu", "test-windows"]

    owns_connection = service_instance is None
    if owns_connection:
        service_instance = connect_vsphere()

    content = service_instance.RetrieveContent()
    container = content.viewManager.CreateContainerView(
        content.rootFolder,
        [vim.VirtualMachine],
        True,
    )

    try:
        return [vm.name for vm in container.view]
    finally:
        container.Destroy()
        if owns_connection:
            disconnect_vsphere(service_instance)


def get_vmware_status():
    if SIMULATION_MODE:
        return {
            "simulation_mode": True,
            "connected": True,
            "host": VCENTER_HOST,
            "port": VCENTER_PORT,
        }

    _require_real_config()
    service_instance = None
    try:
        service_instance = connect_vsphere()
        return {
            "simulation_mode": False,
            "connected": True,
            "host": VCENTER_HOST,
            "port": VCENTER_PORT,
        }
    finally:
        disconnect_vsphere(service_instance)
