# Orange DRS — application complète de démonstration

Application locale Python, sans données Orange réelles. Elle fournit : authentification, données/sites, sélection et import Excel/TXT, projets 5G/SWAP vivants, cellules éditables avec contrôle de version, chat, export Excel, notifications non lues, bilans Plotly et export Word du bilan 5G.

Les tableaux utilisent `streamlit-aggrid` : le tri reste disponible sur les en-têtes et la loupe visible au survol permet une recherche par colonne avec suggestions de valeurs existantes.

## Lancement sous Windows

```powershell
cd "CHEMIN\orange-drs-complete"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

Dans un second terminal :

```powershell
cd "CHEMIN\orange-drs-complete"
.\.venv\Scripts\Activate.ps1
streamlit run frontend/app.py
```

Ouvrir `http://localhost:8501`.

Les deux commandes doivent rester lancées en même temps : FastAPI dans le premier terminal (port 8000), puis Streamlit dans le second terminal (port 8501). Si la page affiche « serveur API non démarré », c'est le premier terminal qui est arrêté : relancer `uvicorn backend.main:app --reload --port 8000`.

Comptes de démonstration : `admin / ChangeMe2026!` et `transport / Transport2026!`.

Dans l'onglet **Bilan**, le bouton **Exporter le bilan Word** crée un `.docx` dynamique avec les trois tableaux de suivi, les en-têtes jaunes et les statuts positifs en vert. Aucune bibliothèque Word supplémentaire n'est nécessaire ; redémarrer simplement FastAPI après la mise à jour.

La première exécution génère automatiquement `data/orange_drs_demo.db` et 60 sites tunisiens fictifs (`ARI_`, `MAN_`, `TUN_`, `SFX_`, `SOU_`) qui respectent le schéma demandé. Pour recréer ces données, arrêter les deux serveurs puis lancer `python -m backend.reset_demo`.

## Sécurité et déploiement

Cette V1 est une démonstration locale. Avant un usage Orange, changer `DRS_SECRET`, supprimer les comptes de démonstration, connecter l'authentification SSO/AD, utiliser la base interne approuvée (PostgreSQL/Oracle/etc.), HTTPS et les sauvegardes DSI. Ne jamais versionner une base contenant des données réelles.
