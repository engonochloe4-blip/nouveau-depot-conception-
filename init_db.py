from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import app  # noqa: E402
from models import db, User  # noqa: E402


def init_database():
    with app.app_context():
        db.create_all()

        if not User.query.filter_by(username="admin").first():
            admin = User(
                username="admin",
                email="admin@vmware.local",
                role="admin",
                is_active=True,
            )
            admin.set_password("admin123")
            db.session.add(admin)

        if not User.query.filter_by(username="user").first():
            user = User(
                username="user",
                email="user@vmware.local",
                role="user",
                is_active=True,
            )
            user.set_password("user123")
            db.session.add(user)

        db.session.commit()


if __name__ == "__main__":
    init_database()
    print("Base de donnees initialisee.")
