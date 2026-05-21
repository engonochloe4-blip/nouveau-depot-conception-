import os
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from dotenv import load_dotenv

from vmware_api import connect_vsphere, list_vms, create_snapshot, restore_snapshot, get_vm_lock_status, acquire_vm_lock, release_vm_lock
from models import db, OperationHistory, VMLock, User

BASE_DIR = Path(__file__).resolve().parent
for env_path in (BASE_DIR.parent / ".env", BASE_DIR / ".env"):
    if env_path.exists():
        load_dotenv(env_path, override=env_path.parent == BASE_DIR)

SIMULATION_MODE = os.getenv("SIMULATION_MODE", "1") == "1"

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///vmware_history.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key-change-in-production-12345")
app.config["SESSION_COOKIE_SECURE"] = False  # True en production HTTPS
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=24)

db.init_app(app)

with app.app_context():
    db.create_all()


# ==================== AUTHENTIFICATION ====================

def login_required(f):
    """DÃ©corateur pour vÃ©rifier que l'utilisateur est connectÃ©."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """DÃ©corateur pour vÃ©rifier que l'utilisateur est admin."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        user = User.query.get(session['user_id'])
        if not user or user.role != 'admin':
            return jsonify({"error": "AccÃ¨s administrateur requis"}), 403
        
        return f(*args, **kwargs)
    return decorated_function


@app.route("/login", methods=["GET", "POST"])
def login():
    """Page et traitement de connexion."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        if not username or not password:
            return render_template("login.html", error="Identifiant et mot de passe requis")
        
        user = User.query.filter_by(username=username).first()
        
        if not user:
            return render_template("login.html", error="Identifiant ou mot de passe incorrect")
        
        if not user.is_active:
            return render_template("login.html", error="Compte dÃ©sactivÃ©")
        
        if not user.check_password(password):
            return render_template("login.html", error="Identifiant ou mot de passe incorrect")
        
        # Mise Ã  jour du dernier login
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # CrÃ©er la session
        session.permanent = True
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        
        return redirect(url_for('index'))
    
    return render_template("login.html")


@app.route("/logout")
def logout():
    """DÃ©connexion."""
    session.clear()
    return redirect(url_for('login'))


@app.route("/api/user")
def get_current_user():
    """RÃ©cupÃ©rer les infos de l'utilisateur actuel."""
    if 'user_id' not in session:
        return jsonify({"error": "Non authentifiÃ©"}), 401
    
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({"error": "Utilisateur non trouvÃ©"}), 404
    
    return jsonify(user.to_dict())


# ==================== DASHBOARD ====================

@app.route("/")
@login_required
def index():
    return render_template("dashboard.html")


@app.route("/vmware/vms")
@login_required
def get_vms():

    try:

        HOST = os.getenv("VCENTER_HOST")
        USER = os.getenv("VCENTER_USERNAME")
        PASSWORD = os.getenv("VCENTER_PASSWORD")

        if not HOST or not USER or not PASSWORD:
            if not SIMULATION_MODE:
                save_history(
                    action="liste_vm",
                    status="erreur",
                    message="VCENTER_HOST, VCENTER_USERNAME ou VCENTER_PASSWORD manquant"
                )
                return jsonify({
                    "error": "VCENTER_HOST, VCENTER_USERNAME et VCENTER_PASSWORD doivent Ãªtre dÃ©finis"
                }), 500

        si = connect_vsphere(HOST, USER, PASSWORD)

        if not si:

            save_history(
                action="liste_vm",
                status="erreur",
                message="Connexion VMware Ã©chouÃ©e"
            )

            return jsonify({
                "error": "Connexion VMware Ã©chouÃ©e"
            }), 500

        vms = list_vms(si)

        save_history(
            action="liste_vm",
            status="succÃ¨s",
            message=f"{len(vms)} VM rÃ©cupÃ©rÃ©e(s)"
        )

        return jsonify({
            "vms": vms
        })

    except Exception as e:

        save_history(
            action="liste_vm",
            status="erreur",
            message=str(e)
        )

        return jsonify({
            "error": str(e)
        }), 500


@app.route("/vmware/status")
@login_required
def vmware_status():
    HOST = os.getenv("VCENTER_HOST")
    USER = os.getenv("VCENTER_USERNAME")
    PASSWORD = os.getenv("VCENTER_PASSWORD")

    if SIMULATION_MODE:
        return jsonify({
            "simulation": True,
            "message": "Mode simulation actif. Pas de connexion rÃ©elle Ã  vCenter.",
            "vcenter_host": HOST,
            "vcenter_username_configured": bool(USER),
            "vcenter_password_configured": bool(PASSWORD),
        })

    try:
        si = connect_vsphere(HOST, USER, PASSWORD)
        return jsonify({
            "simulation": False,
            "connected": bool(si),
            "host": HOST,
        })
    except Exception as e:
        return jsonify({
            "simulation": False,
            "connected": False,
            "error": str(e),
        }), 500


def save_history(action, status, vm_name=None, message=None):
    operation = OperationHistory(
        action=action,
        vm_name=vm_name,
        status=status,
        message=message
    )
    db.session.add(operation)
    db.session.commit()


@app.route("/history")
@login_required
def history():
    query = OperationHistory.query

    action = request.args.get("action")
    vm_name = request.args.get("vm_name")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    if action:
        query = query.filter_by(action=action)

    if vm_name:
        query = query.filter_by(vm_name=vm_name)

    if date_from:
        try:
            start_date = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(OperationHistory.created_at >= start_date)
        except ValueError:
            return jsonify({"error": "date_from doit être au format YYYY-MM-DD"}), 400

    if date_to:
        try:
            end_date = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(OperationHistory.created_at < end_date)
        except ValueError:
            return jsonify({"error": "date_to doit être au format YYYY-MM-DD"}), 400

    operations = query.order_by(OperationHistory.created_at.desc()).all()
    return jsonify(history=[op.to_dict() for op in operations])


@app.route("/vmware/snapshot", methods=["POST"])
@login_required
def create_vm_snapshot():
    try:
        data = request.get_json()
        vm_name = data.get("vm_name")
        snapshot_name = data.get("snapshot_name")
        session_id = data.get("session_id")  # ID de session pour le verrouillage
        
        if not vm_name:
            return jsonify({"error": "vm_name est requis"}), 400
        
        HOST = os.getenv("VCENTER_HOST")
        USER = os.getenv("VCENTER_USERNAME")
        PASSWORD = os.getenv("VCENTER_PASSWORD")
        
        si = connect_vsphere(HOST, USER, PASSWORD)
        result = create_snapshot(vm_name, snapshot_name, service_instance=si, session_id=session_id)
        
        if result.get("success"):
            save_history(
                action="snapshot",
                vm_name=vm_name,
                status="succÃ¨s",
                message=result.get("message")
            )
            return jsonify(result), 200
        else:
            save_history(
                action="snapshot",
                vm_name=vm_name,
                status="erreur",
                message=result.get("error")
            )
            return jsonify(result), 409 if "verrouillÃ©e" in result.get("error", "") else 400
    
    except Exception as e:
        save_history(
            action="snapshot",
            status="erreur",
            message=str(e)
        )
        return jsonify({"error": str(e)}), 500


@app.route("/vmware/restore-snapshot", methods=["POST"])
@login_required
def restore_vm_snapshot():
    try:
        data = request.get_json()
        vm_name = data.get("vm_name")
        snapshot_name = data.get("snapshot_name")
        session_id = data.get("session_id")  # ID de session pour le verrouillage
        
        if not vm_name or not snapshot_name:
            return jsonify({"error": "vm_name et snapshot_name sont requis"}), 400
        
        HOST = os.getenv("VCENTER_HOST")
        USER = os.getenv("VCENTER_USERNAME")
        PASSWORD = os.getenv("VCENTER_PASSWORD")
        
        si = connect_vsphere(HOST, USER, PASSWORD)
        result = restore_snapshot(vm_name, snapshot_name, service_instance=si, session_id=session_id)
        
        if result.get("success"):
            save_history(
                action="restore_snapshot",
                vm_name=vm_name,
                status="succÃ¨s",
                message=result.get("message")
            )
            return jsonify(result), 200
        else:
            save_history(
                action="restore_snapshot",
                vm_name=vm_name,
                status="erreur",
                message=result.get("error")
            )
            return jsonify(result), 409 if "verrouillÃ©e" in result.get("error", "") else 400
    
    except Exception as e:
        save_history(
            action="restore_snapshot",
            status="erreur",
            message=str(e)
        )
        return jsonify({"error": str(e)}), 500


@app.route("/vmware/restore/<vm_name>", methods=["POST"])
@login_required
def restore_vm_snapshot_by_name(vm_name):
    try:
        data = request.get_json(silent=True) or {}
        snapshot_name = data.get("snapshot_name") or request.args.get("snapshot_name")
        session_id = data.get("session_id")  # ID de session pour le verrouillage

        if not snapshot_name:
            return jsonify({"error": "snapshot_name est requis"}), 400

        HOST = os.getenv("VCENTER_HOST")
        USER = os.getenv("VCENTER_USERNAME")
        PASSWORD = os.getenv("VCENTER_PASSWORD")

        si = connect_vsphere(HOST, USER, PASSWORD)
        result = restore_snapshot(vm_name, snapshot_name, service_instance=si, session_id=session_id)

        if result.get("success"):
            save_history(
                action="restore_snapshot",
                vm_name=vm_name,
                status="succÃ¨s",
                message=result.get("message")
            )
            return jsonify(result), 200
        else:
            save_history(
                action="restore_snapshot",
                vm_name=vm_name,
                status="erreur",
                message=result.get("error")
            )
            return jsonify(result), 409 if "verrouillÃ©e" in result.get("error", "") else 400

    except Exception as e:
        save_history(
            action="restore_snapshot",
            status="erreur",
            message=str(e)
        )
        return jsonify({"error": str(e)}), 500


@app.route("/vmware/locks")
@login_required
def get_vm_locks():
    """RÃ©cupÃ¨re tous les verrous actifs."""
    try:
        locks = VMLock.query.filter(VMLock.expires_at > datetime.utcnow()).all()
        return jsonify({
            "locks": [lock.to_dict() for lock in locks]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/vmware/lock/<vm_name>")
@login_required
def get_vm_lock(vm_name):
    """VÃ©rifie le statut de verrouillage d'une VM."""
    try:
        lock_status = get_vm_lock_status(vm_name)
        return jsonify(lock_status)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/vmware/unlock/<vm_name>", methods=["POST"])
@login_required
def unlock_vm(vm_name):
    """Force la libÃ©ration d'un verrou (pour les administrateurs)."""
    try:
        data = request.get_json(silent=True) or {}
        session_id = data.get("session_id")

        if not session_id:
            return jsonify({"error": "session_id requis"}), 400

        result = release_vm_lock(vm_name, session_id)
        return jsonify(result), 200 if result.get("success") else 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/vmware/stats")
@login_required
def get_stats():
    try:
        # Total operations
        total_ops = OperationHistory.query.count()
        
        # Operations by status
        success = OperationHistory.query.filter_by(status="succÃ¨s").count()
        errors = OperationHistory.query.filter_by(status="erreur").count()
        
        # Operations by action
        snapshots = OperationHistory.query.filter_by(action="snapshot").count()
        restores = OperationHistory.query.filter_by(action="restore_snapshot").count()
        lists = OperationHistory.query.filter_by(action="liste_vm").count()
        
        # Get VMs
        HOST = os.getenv("VCENTER_HOST")
        USER = os.getenv("VCENTER_USERNAME")
        PASSWORD = os.getenv("VCENTER_PASSWORD")
        
        si = connect_vsphere(HOST, USER, PASSWORD)
        vms_data = list_vms(si)
        
        vms_on = sum(1 for vm in vms_data if isinstance(vm, dict) and vm.get("power_state") == "poweredOn")
        vms_off = len(vms_data) - vms_on if isinstance(vms_data[0], dict) else 0
        
        return jsonify({
            "total_vms": len(vms_data),
            "vms_on": vms_on,
            "vms_off": vms_off,
            "total_operations": total_ops,
            "successful_operations": success,
            "failed_operations": errors,
            "snapshots_created": snapshots,
            "snapshots_restored": restores,
            "vms_listed": lists,
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", "5000")))


