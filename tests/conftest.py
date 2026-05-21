import os
import sys
from pathlib import Path

import pytest


BASE_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = BASE_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("SIMULATION_MODE", "1")
os.environ.setdefault("VCENTER_HOST", "127.0.0.1")
os.environ.setdefault("VCENTER_USERNAME", "tester")
os.environ.setdefault("VCENTER_PASSWORD", "tester")
os.environ.setdefault("SECRET_KEY", "pytest-secret-key")

import app as app_module  # noqa: E402
import vmware_api  # noqa: E402
from models import OperationHistory, User, VMLock, db  # noqa: E402


app_module.SIMULATION_MODE = True
vmware_api.SIMULATION_MODE = True


@pytest.fixture()
def flask_app():
    app = app_module.app
    app.config.update(TESTING=True)

    with app.app_context():
        db.drop_all()
        db.create_all()

        admin = User(username="admin", email="admin@vmware.local", role="admin", is_active=True)
        admin.set_password("admin123")

        user = User(username="user", email="user@vmware.local", role="user", is_active=True)
        user.set_password("user123")

        db.session.add_all([admin, user])
        db.session.commit()

        yield app

        db.session.remove()


@pytest.fixture()
def client(flask_app):
    return flask_app.test_client()


@pytest.fixture()
def db_session(flask_app):
    with flask_app.app_context():
        yield db


@pytest.fixture()
def models():
    return {
        "OperationHistory": OperationHistory,
        "User": User,
        "VMLock": VMLock,
        "db": db,
    }
