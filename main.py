import os
import socket
import ssl

from pyVim.connect import Disconnect, SmartConnect
from pyVmomi import vim

SIMULATION_MODE = os.getenv("SIMULATION_MODE", "1") == "1"
VCENTER_HOST = os.getenv("VCENTER_HOST", "IP_OU_HOST_VMWARE")
USERNAME = os.getenv("VCENTER_USERNAME", "ton_user")
PASSWORD = os.getenv("VCENTER_PASSWORD", "ton_password")


def connect_vsphere():
    if SIMULATION_MODE:
        print("Simulation connexion VMware")
        return "fake_connection"

    if not VCENTER_HOST or VCENTER_HOST == "IP_OU_HOST_VMWARE":
        raise RuntimeError("VCENTER_HOST n'est pas defini. Configure une IP ou un nom DNS valide.")
    if not USERNAME or USERNAME == "ton_user":
        raise RuntimeError("VCENTER_USERNAME n'est pas defini.")
    if not PASSWORD or PASSWORD == "ton_password":
        raise RuntimeError("VCENTER_PASSWORD n'est pas defini.")

    context = ssl._create_unverified_context()
    try:
        return SmartConnect(
            host=VCENTER_HOST,
            user=USERNAME,
            pwd=PASSWORD,
            sslContext=context,
        )
    except socket.gaierror as exc:
        raise RuntimeError(
            f"Impossible de resoudre '{VCENTER_HOST}'. "
            "Remplace VCENTER_HOST par une IP ou un nom DNS valide."
        ) from exc


def list_vms(si):
    if SIMULATION_MODE:
        print("VM: test-ubuntu")
        print("VM: test-windows")
        return

    content = si.RetrieveContent()
    container = content.viewManager.CreateContainerView(
        content.rootFolder,
        [vim.VirtualMachine],
        True,
    )

    try:
        for vm in container.view:
            print("VM:", vm.name)
    finally:
        container.Destroy()


if __name__ == "__main__":
    si = None
    try:
        si = connect_vsphere()
        print("Connecte a VMware")
        list_vms(si)
    except Exception as exc:
        print(f"Erreur: {exc}")
    finally:
        if si is not None and not SIMULATION_MODE:
            Disconnect(si)
