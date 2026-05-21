# supervision-vmware

## Connexion VMware

Ce projet contient une base Flask qui peut tester la connexion vSphere via `pyVmomi`.

### Variables d'environnement

- `SIMULATION_MODE=1` pour simuler la connexion
- `SIMULATION_MODE=0` pour utiliser le vrai vCenter
- `VCENTER_HOST`
- `VCENTER_USERNAME`
- `VCENTER_PASSWORD`
- `VCENTER_PORT` optionnel, defaut `443`

Le backend charge automatiquement les fichiers `.env` du projet :

- `backend/.env` a priorite sur
- `.env` a la racine du depot

Exemple minimal pour un acces reel :

```env
SIMULATION_MODE=0
VCENTER_HOST=vcenter.mon-domaine.local
VCENTER_USERNAME=administrator@vsphere.local
VCENTER_PASSWORD=mon_mot_de_passe
VCENTER_PORT=443
```

### Installation

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Initialisation de la base

```powershell
python init_db.py
```

### Lancement Flask

```powershell
python backend/app.py
```

### Routes

- `GET /`
- `GET /vmware/status`
- `GET /vmware/vms`

### Mode simulation

- Active par defaut via `SIMULATION_MODE=1`
- Permet de tester l'API sans acces au vCenter
- Mettre `SIMULATION_MODE=0` pour basculer en mode reel lorsque les identifiants sont disponibles

## Deploiement Docker

### Demarrage rapide

```powershell
docker compose up --build
```

### Variables d'environnement

- Copier `.env.example` en `.env` si vous voulez utiliser un vrai vCenter
- Laisser `SIMULATION_MODE=1` pour une demonstration sans vCenter
- La base SQLite est persistee via le volume `./backend/instance:/app/backend/instance`

### Ce que fait le conteneur

- Installe les dependances Python
- Initialise la base avec `python init_db.py`
- Lance Flask sur `0.0.0.0:5000`

### Etat actuel

- API Flask fonctionnelle
- Mode simulation pour travailler sans vCenter
- Connexion reelle vSphere prete a etre utilisee quand les variables d'environnement sont renseignees

## UML et Sauvegarde

- Diagrammes UML sources dans `docs/uml/`
- Sauvegarde SQLite horodatee via `scripts/backup_db.py`
- Le dossier `backups/` est ignore par Git
