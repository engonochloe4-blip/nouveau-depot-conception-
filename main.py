from vmware_client import connect_vsphere, disconnect_vsphere, list_vms


if __name__ == "__main__":
    si = None
    try:
        si = connect_vsphere()
        print("Connecte a VMware")
        for vm_name in list_vms(si):
            print("VM:", vm_name)
    except Exception as exc:
        print(f"Erreur: {exc}")
    finally:
        disconnect_vsphere(si)
