from sqlalchemy import inspect, text
from .database import Base, engine, SessionLocal
from .models import User, Site
from .security import hash_password

def seed_demo():
    Base.metadata.create_all(engine)
    # Petite migration compatible avec une base de démonstration créée avant
    # l'ajout de l'objectif projet. Une vraie base utilisera Alembic/DSI.
    with engine.begin() as connection:
        if "projects" in inspect(engine).get_table_names():
            columns={c["name"] for c in inspect(engine).get_columns("projects")}
            if "objectif" not in columns:
                connection.execute(text("ALTER TABLE projects ADD COLUMN objectif INTEGER DEFAULT 0"))
        if "project_items" in inspect(engine).get_table_names():
            item_columns={c["name"] for c in inspect(engine).get_columns("project_items")}
            for column in ("kpis", "status", "statut_ouverture_meteo"):
                if column not in item_columns:
                    connection.execute(text(f"ALTER TABLE project_items ADD COLUMN {column} TEXT"))
    with SessionLocal() as db:
        if not db.query(User).first():
            db.add_all([User(username="admin", password_hash=hash_password("ChangeMe2026!"), role="admin"), User(username="transport", password_hash=hash_password("Transport2026!"), role="editor")])
        if not db.query(Site).first():
            rows=[]
            regions=[("ARI","Ariana","Raoued",["El Medina El Fadhila","Jaafer","Soukra"]),("MAN","Manouba","Manouba",["Denden","Douar Hicher","Oued Ellil"]),("TUN","Tunis","Tunis",["Carthage","Lac","El Menzah"]),("SFX","Sfax","Sfax",["Sakiet Ezzit","El Ain","Centre Ville"]),("SOU","Sousse","Sousse",["Hammam Sousse","Khezama","Centre Ville"])]
            for i in range(1, 61):
                prefix,gov,deleg,sectors=regions[(i-1)%len(regions)]; arch=["TF","BH","FO"][i%3]; five="✓" if i%3 else "✗"
                rows.append(Site(site_code=f"{prefix}_{i+2:04d}", architecture=arch, gouvernorat=gov, delegation=deleg, secteur=sectors[i%len(sectors)], statut="Actif" if i%7 else "Inactif", date_me="2010-02", latitude=36.8+i/1000, longitude=10.1+i/1000, has_2g="✓", has_3g="✓", has_4g="✓", has_4g_tdd="✓" if i%2 else "✗", has_5g=five, nb_g900=4, nb_g1800=0, nb_u900=8, nb_u2100=0, nb_l800=4, nb_l1800=4, nb_l2100=4, nb_ltetdd=6, nb_nr700=0, nb_nr1800=0, nb_nr3500=3 if five=="✓" else 0, nb_trx_2g=4, type_transmission="FO" if arch=="FO" else "FH", hauteur_gc_m=9, type_gc="Mât", description_gc="Démo — aucune donnée réelle", cohabitation="Orange", sharing="site sharing", type_site_topo="Terminal", capacite_mbps=1024, nb_rru=19, has5g_rru=five, has_aau=five, fabricant_ran="Huawei", oss_group="SSVOK/FN8OK", priorite="P0" if i%5==0 else "P1", nb_secteurs=4, nb_cells_2g=4, nb_cells_3g=8, nb_cells_4g=18, nb_cells_5g=3 if five=="✓" else 0))
            db.add_all(rows)
        db.commit()
