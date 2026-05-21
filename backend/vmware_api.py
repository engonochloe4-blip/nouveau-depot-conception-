import os
import ssl
import uuid
import traceback
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from pyVim.connect import SmartConnect, Disconnect

BASE_DIR = Path(__file__).resolve().parent
for env_path in (BASE_DIR.parent / ".env", BASE_DIR / ".env"):
    if env_path.exists():
        load_dotenv(env_path, override=env_path.parent == BASE_DIR)

SIMULATION_MODE = os.getenv("SIMULATION_MODE", "1") == "1"
VCENTER_PORT = int(os.getenv("VCENTER_PORT", "443"))


def connect_vsphere(host=None, user=None, password=None, port=None):
    host = host or os.getenv("VCENTER_HOST")
    user = user or os.getenv("VCENTER_USERNAME")
    password = password or os.getenv("VCENTER_PASSWORD")
    port = int(port or os.getenv("VCENTER_PORT", VCENTER_PORT))

    if SIMULATION_MODE:
        return "simulation"

    if not host or not user or not password:
        raise RuntimeError("VCENTER_HOST, VCENTER_USERNAME et VCENTER_PASSWORD doivent être définis")

    context = ssl._create_unverified_context()

    try:
        si = SmartConnect(
            host=host,
            user=user,
            pwd=password,
            port=port,
            sslContext=context
        )
        return si
    except Exception as exc:
        raise RuntimeError(
            f"Erreur de connexion vCenter ({host}:{port}) : {exc}\n{traceback.format_exc()}"
        ) from exc


def list_vms(service_instance=None):
    if SIMULATION_MODE or service_instance == "simulation":
        return [
            {
                "name": "VM-test",
                "power_state": "poweredOn",
                "cpu": 2,
                "memory_mb": 4096
            }
        ]

    owns_connection = service_instance is None
    if owns_connection:
        service_instance = connect_vsphere()

    try:
        from pyVmomi import vim

        content = service_instance.RetrieveContent()
        container = content.viewManager.CreateContainerView(
            content.rootFolder,
            [vim.VirtualMachine],
            True,
        )

        try:
            vms = []
            for vm in container.view:
                vms.append(
                    {
                        "name": vm.name,
                        "power_state": vm.runtime.powerState,
                        "cpu": vm.config.hardware.numCPU,
                        "memory_mb": vm.config.hardware.memoryMB,
                    }
                )
            return vms
        finally:
            container.Destroy()
    finally:
        if owns_connection and service_instance is not None:
            Disconnect(service_instance)


def acquire_vm_lock(vm_name, operation, session_id=None):
    """Acquiert un verrou pour une VM."""
    from models import db, VMLock

    if session_id is None:
        session_id = str(uuid.uuid4())

    try:
        # Nettoyer les verrous expirés
        expired_locks = VMLock.query.filter(VMLock.expires_at < datetime.utcnow()).all()
        for lock in expired_locks:
            db.session.delete(lock)

        # Vérifier si la VM est déjà verrouillée
        existing_lock = VMLock.query.filter_by(vm_name=vm_name).first()
        if existing_lock and not existing_lock.is_expired():
            return {
                "success": False,
                "error": f"VM '{vm_name}' est déjà verrouillée pour l'opération '{existing_lock.operation}'",
                "locked_by": existing_lock.locked_by,
                "expires_at": existing_lock.expires_at.strftime("%Y-%m-%d %H:%M:%S")
            }

        # Créer un nouveau verrou
        lock = VMLock(
            vm_name=vm_name,
            locked_by=session_id,
            operation=operation,
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )
        db.session.add(lock)
        db.session.commit()

        return {
            "success": True,
            "session_id": session_id,
            "message": f"Verrou acquis pour {vm_name}"
        }

    except Exception as e:
        db.session.rollback()
        return {
            "success": False,
            "error": f"Erreur lors de l'acquisition du verrou: {str(e)}"
        }


def release_vm_lock(vm_name, session_id):
    """Libère le verrou d'une VM."""
    from models import db, VMLock

    try:
        lock = VMLock.query.filter_by(vm_name=vm_name, locked_by=session_id).first()
        if lock:
            db.session.delete(lock)
            db.session.commit()
            return {
                "success": True,
                "message": f"Verrou libéré pour {vm_name}"
            }
        else:
            return {
                "success": False,
                "error": f"Aucun verrou trouvé pour {vm_name} avec session {session_id}"
            }

    except Exception as e:
        db.session.rollback()
        return {
            "success": False,
            "error": f"Erreur lors de la libération du verrou: {str(e)}"
        }


def get_vm_lock_status(vm_name):
    """Vérifie le statut de verrouillage d'une VM."""
    try:
        from models import VMLock
        lock = VMLock.query.filter_by(vm_name=vm_name).first()
        if lock and not lock.is_expired():
            return {
                "locked": True,
                "operation": lock.operation,
                "locked_by": lock.locked_by,
                "expires_at": lock.expires_at.strftime("%Y-%m-%d %H:%M:%S")
            }
        else:
            return {"locked": False}

    except Exception as e:
        return {
            "locked": False,
            "error": f"Erreur lors de la vérification du verrou: {str(e)}"
        }


def create_snapshot(vm_name, snapshot_name=None, description="Snapshot créé automatiquement", service_instance=None, session_id=None):
    """Crée un snapshot d'une VM."""
    
    # Acquérir le verrou
    lock_result = acquire_vm_lock(vm_name, "create_snapshot", session_id)
    if not lock_result.get("success"):
        return {
            "success": False,
            "vm_name": vm_name,
            "error": lock_result.get("error")
        }
    
    actual_session_id = lock_result.get("session_id")
    
    if SIMULATION_MODE:
        release_vm_lock(vm_name, actual_session_id)
        return {
            "success": True,
            "vm_name": vm_name,
            "snapshot_name": snapshot_name or f"snapshot-{vm_name}",
            "message": f"Snapshot simulation créé pour {vm_name}"
        }
    
    if not service_instance:
        service_instance = connect_vsphere()
    
    try:
        from pyVmomi import vim
        
        content = service_instance.RetrieveContent()
        container = content.viewManager.CreateContainerView(
            content.rootFolder,
            [vim.VirtualMachine],
            True,
        )
        
        vm = None
        for virtual_machine in container.view:
            if virtual_machine.name == vm_name:
                vm = virtual_machine
                break
        
        container.Destroy()
        
        if not vm:
            raise RuntimeError(f"VM '{vm_name}' non trouvée")
        
        snapshot_name = snapshot_name or f"snapshot-{vm_name}-{int(__import__('time').time())}"
        
        task = vm.CreateSnapshot_Task(
            name=snapshot_name,
            description=description,
            memory=True,
            quiesce=False
        )
        
        # Attendre que la tâche se termine
        while task.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:
            __import__('time').sleep(0.5)
        
        if task.info.state == vim.TaskInfo.State.success:
            # Libérer le verrou en cas de succès
            release_vm_lock(vm_name, actual_session_id)
            return {
                "success": True,
                "vm_name": vm_name,
                "snapshot_name": snapshot_name,
                "message": f"Snapshot '{snapshot_name}' créé pour {vm_name}"
            }
        else:
            # Libérer le verrou en cas d'erreur
            release_vm_lock(vm_name, actual_session_id)
            raise RuntimeError(f"Erreur lors de la création du snapshot: {task.info.error}")
    
    except Exception as e:
        # Libérer le verrou en cas d'exception
        release_vm_lock(vm_name, actual_session_id)
        return {
            "success": False,
            "vm_name": vm_name,
            "error": str(e)
        }


def restore_snapshot(vm_name, snapshot_name, service_instance=None, session_id=None):
    """Restaure une VM à partir d'un snapshot."""
    
    # Acquérir le verrou
    lock_result = acquire_vm_lock(vm_name, "restore_snapshot", session_id)
    if not lock_result.get("success"):
        return {
            "success": False,
            "vm_name": vm_name,
            "snapshot_name": snapshot_name,
            "error": lock_result.get("error")
        }
    
    actual_session_id = lock_result.get("session_id")
    
    if SIMULATION_MODE:
        release_vm_lock(vm_name, actual_session_id)
        return {
            "success": True,
            "vm_name": vm_name,
            "snapshot_name": snapshot_name,
            "message": f"Snapshot '{snapshot_name}' restauré pour {vm_name} (simulation)"
        }
    
    if not service_instance:
        service_instance = connect_vsphere()
    
    try:
        from pyVmomi import vim
        
        content = service_instance.RetrieveContent()
        container = content.viewManager.CreateContainerView(
            content.rootFolder,
            [vim.VirtualMachine],
            True,
        )
        
        vm = None
        for virtual_machine in container.view:
            if virtual_machine.name == vm_name:
                vm = virtual_machine
                break
        
        container.Destroy()
        
        if not vm:
            raise RuntimeError(f"VM '{vm_name}' non trouvée")
        
        # Chercher le snapshot
        snapshot = None
        if vm.snapshot:
            for snap in vm.snapshot.rootSnapshotList:
                if snap.name == snapshot_name:
                    snapshot = snap.snapshot
                    break
        
        if not snapshot:
            raise RuntimeError(f"Snapshot '{snapshot_name}' non trouvé pour {vm_name}")
        
        # Restaurer le snapshot
        task = snapshot.RevertToSnapshot_Task()
        
        # Attendre que la tâche se termine
        while task.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:
            __import__('time').sleep(0.5)
        
        if task.info.state == vim.TaskInfo.State.success:
            # Libérer le verrou en cas de succès
            release_vm_lock(vm_name, actual_session_id)
            return {
                "success": True,
                "vm_name": vm_name,
                "snapshot_name": snapshot_name,
                "message": f"Snapshot '{snapshot_name}' restauré pour {vm_name}"
            }
        else:
            # Libérer le verrou en cas d'erreur
            release_vm_lock(vm_name, actual_session_id)
            raise RuntimeError(f"Erreur lors de la restauration du snapshot: {task.info.error}")
    
    except Exception as e:
        # Libérer le verrou en cas d'exception
        release_vm_lock(vm_name, actual_session_id)
        return {
            "success": False,
            "vm_name": vm_name,
            "snapshot_name": snapshot_name,
            "error": str(e)
        }
