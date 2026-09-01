from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(20), default="editor")

class Site(Base):
    __tablename__ = "sites"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    architecture: Mapped[str | None] = mapped_column(String(20))
    gouvernorat: Mapped[str] = mapped_column(String(60)); delegation: Mapped[str] = mapped_column(String(80)); secteur: Mapped[str] = mapped_column(String(100)); statut: Mapped[str] = mapped_column(String(30))
    date_me: Mapped[str | None] = mapped_column(String(20)); latitude: Mapped[float | None] = mapped_column(); longitude: Mapped[float | None] = mapped_column()
    has_2g: Mapped[str] = mapped_column(String(10)); has_3g: Mapped[str] = mapped_column(String(10)); has_4g: Mapped[str] = mapped_column(String(10)); has_4g_tdd: Mapped[str] = mapped_column(String(10)); has_5g: Mapped[str] = mapped_column(String(10))
    nb_g900: Mapped[int] = mapped_column(default=0); nb_g1800: Mapped[int] = mapped_column(default=0); nb_u900: Mapped[int] = mapped_column(default=0); nb_u2100: Mapped[int] = mapped_column(default=0); nb_l800: Mapped[int] = mapped_column(default=0); nb_l1800: Mapped[int] = mapped_column(default=0); nb_l2100: Mapped[int] = mapped_column(default=0); nb_ltetdd: Mapped[int] = mapped_column(default=0); nb_nr700: Mapped[int] = mapped_column(default=0); nb_nr1800: Mapped[int] = mapped_column(default=0); nb_nr3500: Mapped[int] = mapped_column(default=0); nb_trx_2g: Mapped[int] = mapped_column(default=0)
    type_transmission: Mapped[str | None] = mapped_column(String(20)); hauteur_gc_m: Mapped[float | None] = mapped_column(); type_gc: Mapped[str | None] = mapped_column(String(50)); description_gc: Mapped[str | None] = mapped_column(Text); cohabitation: Mapped[str | None] = mapped_column(String(80)); sharing: Mapped[str | None] = mapped_column(String(80)); type_site_topo: Mapped[str | None] = mapped_column(String(80)); capacite_mbps: Mapped[float | None] = mapped_column(); nb_rru: Mapped[int] = mapped_column(default=0); has5g_rru: Mapped[str] = mapped_column(String(10)); has_aau: Mapped[str] = mapped_column(String(10)); fabricant_ran: Mapped[str | None] = mapped_column(String(80)); oss_group: Mapped[str | None] = mapped_column(String(80)); priorite: Mapped[str | None] = mapped_column(String(20)); nb_secteurs: Mapped[int] = mapped_column(default=0); nb_cells_2g: Mapped[int] = mapped_column(default=0); nb_cells_3g: Mapped[int] = mapped_column(default=0); nb_cells_4g: Mapped[int] = mapped_column(default=0); nb_cells_5g: Mapped[int] = mapped_column(default=0)
    version: Mapped[int] = mapped_column(Integer, default=1); updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow); updated_by: Mapped[str] = mapped_column(String(80), default="system")

class SiteHistory(Base):
    __tablename__ = "site_history"
    id: Mapped[int] = mapped_column(primary_key=True); site_id: Mapped[int] = mapped_column(ForeignKey("sites.id")); field: Mapped[str] = mapped_column(String(80)); old_value: Mapped[str | None] = mapped_column(Text); new_value: Mapped[str | None] = mapped_column(Text); author: Mapped[str] = mapped_column(String(80)); changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True); name: Mapped[str] = mapped_column(String(120), unique=True); type: Mapped[str] = mapped_column(String(10)); objectif: Mapped[int] = mapped_column(Integer, default=0); created_by: Mapped[str] = mapped_column(String(80)); created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ProjectItem(Base):
    __tablename__ = "project_items"
    id: Mapped[int] = mapped_column(primary_key=True); project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True); site_code: Mapped[str] = mapped_column(String(80), index=True)
    type_5g: Mapped[str | None] = mapped_column(String(80)); config: Mapped[str | None] = mapped_column(String(100)); planning: Mapped[str | None] = mapped_column(String(20)); type_de_site: Mapped[str | None] = mapped_column(String(80)); supports_gc: Mapped[str | None] = mapped_column(String(30)); etat_deploiement: Mapped[str | None] = mapped_column(String(50)); swap_vers_tf: Mapped[str | None] = mapped_column(String(50)); besoin_lld_ip: Mapped[str | None] = mapped_column(String(30)); besoin_wo_radio: Mapped[str | None] = mapped_column(String(30)); besoin_lld_radio: Mapped[str | None] = mapped_column(String(30)); owner: Mapped[str | None] = mapped_column(String(80)); priorite: Mapped[str | None] = mapped_column(String(20)); hw: Mapped[str | None] = mapped_column(String(100)); meteo: Mapped[str | None] = mapped_column(String(100)); plan_action: Mapped[str | None] = mapped_column(Text); gc: Mapped[str | None] = mapped_column(String(30)); kpis: Mapped[str | None] = mapped_column(Text); status: Mapped[str | None] = mapped_column(Text); statut_ouverture_meteo: Mapped[str | None] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(default=1); updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow); updated_by: Mapped[str] = mapped_column(String(80), default="system")

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True); project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True); author: Mapped[str] = mapped_column(String(80)); body: Mapped[str] = mapped_column(Text, default=""); sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow); attachment_name: Mapped[str | None] = mapped_column(String(200)); attachment_data: Mapped[bytes | None] = mapped_column(LargeBinary)

class ProjectRead(Base):
    __tablename__ = "project_reads"
    id: Mapped[int] = mapped_column(primary_key=True); project_id: Mapped[int] = mapped_column(ForeignKey("projects.id")); username: Mapped[str] = mapped_column(String(80)); last_message_id: Mapped[int] = mapped_column(default=0)
