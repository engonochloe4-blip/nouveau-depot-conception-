# supervision-vmware

## Connexion VMware

Ce projet contient maintenant une base Flask qui peut tester la connexion vSphere via pyVmomi.

### Variables d'environnement

- `SIMULATION_MODE=1` pour simuler la connexion
- `VCENTER_HOST`
- `VCENTER_USERNAME`
- `VCENTER_PASSWORD`
- `VCENTER_PORT` optionnel, défaut `443`

### Installation

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Lancement Flask

```powershell
.\.venv\Scripts\python.exe backend\app.py
```

### Routes

- `GET /`
- `GET /vmware/status`
- `GET /vmware/vms`
