from datetime import datetime
from io import BytesIO
from typing import Any
import pandas as pd
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from .database import get_db
from .bilan_docx import build_bilan_5g_docx
from .models import Message, Project, ProjectItem, ProjectRead, Site, SiteHistory, User
from .security import current_user, make_token, verify_password
from .seed_demo import seed_demo

app=FastAPI(title="Orange DRS", version="1.0")
MONTHS=["Janvier","Février","Mars","Avril","Mai","Juin","Juillet","Août","Septembre","Octobre","Novembre","Décembre"]
SITE_EDIT={c.name for c in Site.__table__.columns if c.name not in {"id","site_code","version","updated_at","updated_by"}}
SITE_CREATE={c.name for c in Site.__table__.columns if c.name not in {"id","version","updated_at","updated_by"}}
ITEM_5G={"site_code","type_5g","config","planning","type_de_site","supports_gc","etat_deploiement","swap_vers_tf","besoin_lld_ip","besoin_wo_radio","besoin_lld_radio","owner","priorite","hw","meteo","plan_action","gc","kpis","status","statut_ouverture_meteo"}
ITEM_SWAP={"site_code","hw","meteo","plan_action","gc","priorite","besoin_lld_ip","besoin_lld_radio"}

class Login(BaseModel): username:str; password:str
class Change(BaseModel): expected_version:int; values:dict[str,Any]
class NewProject(BaseModel): name:str=Field(min_length=2,max_length=120); type:str; site_codes:list[str]; objectif:int=Field(default=0,ge=0)
class AddSites(BaseModel): site_codes:list[str]
class NewMessage(BaseModel): body:str=""; attach_export:bool=False
class NewSite(BaseModel): values:dict[str,Any]
class BulkSites(BaseModel): records:list[dict[str,Any]]
class DeleteSites(BaseModel): ids:list[int]

@app.on_event("startup")
def init(): seed_demo()
def role(db,u):
    user=db.scalar(select(User).where(User.username==u)); return user.role if user else "viewer"
def editor(db,u):
    if role(db,u) not in {"admin","editor","manager"}: raise HTTPException(403,"Droit de modification requis")
def project_or_404(db,pid):
    p=db.get(Project,pid)
    if not p: raise HTTPException(404,"Projet introuvable")
    return p
def export_bytes(db,pid):
    p=project_or_404(db,pid); rows=db.scalars(select(ProjectItem).where(ProjectItem.project_id==pid)).all(); df=pd.DataFrame([{c.name:getattr(x,c.name) for c in ProjectItem.__table__.columns if c.name not in {"id","project_id","version","updated_at","updated_by"}} for x in rows]); out=BytesIO(); df.to_excel(out,index=False,engine="openpyxl",sheet_name=p.name[:31]); return out.getvalue()
def clean_values(values:dict[str,Any], allowed:set[str]) -> dict[str,Any]:
    """Écarte les colonnes inconnues et convertit les valeurs Excel vides en None."""
    # Accepte les titres courants Excel : Architecture, Site Code, llatitude…
    aliases={"site_name":"site_code",
             "architecture":"architecture","llatitude":"latitude","longitude":"longitude"}
    normalized={}
    for key,value in values.items():
        name=str(key).strip().lower().replace("-","_").replace(" ","_")
        normalized[aliases.get(name,name)]=value
    values=normalized
    bad=set(values)-allowed
    if bad: raise HTTPException(400, f"Colonnes interdites : {', '.join(sorted(bad))}")
    return {k:(None if pd.isna(v) else v) for k,v in values.items()}
def site_defaults(values:dict[str,Any]) -> dict[str,Any]:
    """Rend possible la création manuelle sans devoir saisir les 45 colonnes."""
    defaults={"architecture":"", "gouvernorat":"", "delegation":"", "secteur":"", "statut":"Actif",
              "has_2g":"✗","has_3g":"✗","has_4g":"✗","has_4g_tdd":"✗","has_5g":"✗",
              "has5g_rru":"✗","has_aau":"✗"}
    for col in Site.__table__.columns:
        if col.name.startswith("nb_"):
            defaults[col.name]=0
    defaults.update(values)
    return defaults

@app.post("/auth/login")
def login(body:Login,db:Session=Depends(get_db)):
    u=db.scalar(select(User).where(User.username==body.username))
    if not u or not verify_password(body.password,u.password_hash): raise HTTPException(401,"Identifiants incorrects")
    return {"token":make_token(u.username),"username":u.username,"role":u.role}

@app.get("/sites")
def sites(db:Session=Depends(get_db),user:str=Depends(current_user)):
    return db.scalars(select(Site).order_by(Site.site_code)).all()
@app.post("/sites")
def create_site(body:NewSite,db:Session=Depends(get_db),user:str=Depends(current_user)):
    editor(db,user); values=site_defaults(clean_values(body.values,SITE_CREATE)); code=str(values.get("site_code") or "").strip().upper()
    if not code: raise HTTPException(400,"site_code est obligatoire")
    if db.scalar(select(Site.id).where(Site.site_code==code)): raise HTTPException(409,f"Le site {code} existe déjà")
    values["site_code"]=code; values["updated_by"]=user
    site=Site(**values); db.add(site); db.commit(); db.refresh(site); return site
@app.post("/sites/import")
def import_sites(body:BulkSites,db:Session=Depends(get_db),user:str=Depends(current_user)):
    """Import contrôlé : les doublons ne sont pas écrasés et sont signalés."""
    editor(db,user); created=[]; duplicates=[]; errors=[]
    for index, record in enumerate(body.records, start=1):
        try:
            values=site_defaults(clean_values(record,SITE_CREATE)); code=str(values.get("site_code") or "").strip().upper()
            if not code: errors.append(f"Ligne {index} : site_code absent"); continue
            if db.scalar(select(Site.id).where(Site.site_code==code)): duplicates.append(code); continue
            values["site_code"]=code; values["updated_by"]=user; db.add(Site(**values)); created.append(code)
        except HTTPException as exc: errors.append(f"Ligne {index} : {exc.detail}")
    db.commit(); return {"created":created,"duplicates":duplicates,"errors":errors}
@app.delete("/sites")
def delete_sites(body:DeleteSites,db:Session=Depends(get_db),user:str=Depends(current_user)):
    editor(db,user)
    if not body.ids: raise HTTPException(400,"Aucun site sélectionné")
    rows=db.scalars(select(Site).where(Site.id.in_(body.ids))).all(); codes=[s.site_code for s in rows]
    for site in rows: db.delete(site)
    db.commit(); return {"deleted":codes}
@app.put("/sites/{site_id}")
def change_site(site_id:int,body:Change,db:Session=Depends(get_db),user:str=Depends(current_user)):
    editor(db,user); bad=set(body.values)-SITE_EDIT
    if bad: raise HTTPException(400,f"Colonnes interdites: {', '.join(bad)}")
    old=db.get(Site,site_id)
    if not old: raise HTTPException(404,"Site introuvable")
    values={k:v for k,v in body.values.items() if getattr(old,k)!=v}
    if not values: return old
    # Capture avant l'UPDATE : SQLAlchemy peut synchroniser l'objet en mémoire.
    old_values={k:getattr(old,k) for k in values}
    result=db.execute(update(Site).where(Site.id==site_id,Site.version==body.expected_version).values(**values,version=Site.version+1,updated_at=datetime.utcnow(),updated_by=user))
    if result.rowcount!=1: db.rollback(); raise HTTPException(409,"Cette fiche vient d'être modifiée. Actualise avant de valider.")
    for k,v in values.items(): db.add(SiteHistory(site_id=site_id,field=k,old_value=str(old_values[k]),new_value=str(v),author=user))
    db.commit(); return db.get(Site,site_id)

@app.get("/projects")
def projects(db:Session=Depends(get_db),user:str=Depends(current_user)):
    result=[]
    for p in db.scalars(select(Project).order_by(Project.created_at.desc())):
        last=db.scalar(select(func.max(Message.id)).where(Message.project_id==p.id)) or 0; read=db.scalar(select(ProjectRead.last_message_id).where(ProjectRead.project_id==p.id,ProjectRead.username==user)) or 0
        unread=db.scalar(select(func.count()).select_from(Message).where(Message.project_id==p.id,Message.id>read,Message.author!=user)) or 0
        result.append({"id":p.id,"name":p.name,"type":p.type,"objectif":p.objectif,"created_by":p.created_by,"created_at":p.created_at,"sites":db.scalar(select(func.count()).select_from(ProjectItem).where(ProjectItem.project_id==p.id)),"unread":unread})
    return result
@app.post("/projects")
def create_project(body:NewProject,db:Session=Depends(get_db),user:str=Depends(current_user)):
    editor(db,user)
    if body.type not in {"5g","swap"}: raise HTTPException(400,"Type 5g ou swap attendu")
    if db.scalar(select(Project).where(Project.name==body.name.strip())): raise HTTPException(409,"Ce nom existe déjà")
    p=Project(name=body.name.strip(),type=body.type,objectif=body.objectif or len(body.site_codes),created_by=user); db.add(p); db.flush(); add_items(db,p,list(dict.fromkeys(body.site_codes)),user); db.flush(); data=export_bytes(db,p.id); db.add(Message(project_id=p.id,author="Système",body="Projet créé. Export initial des sites sélectionnés.",attachment_name=f"{p.name}_initial.xlsx",attachment_data=data)); db.commit(); return {"id":p.id}
def add_items(db,p,codes,user):
    existing=set(db.scalars(select(ProjectItem.site_code).where(ProjectItem.project_id==p.id)))
    sites={s.site_code:s for s in db.scalars(select(Site).where(Site.site_code.in_(codes))).all()}
    for code in codes:
        if not code or code in existing: continue
        s=sites.get(code); arch=(s.architecture if s else None)
        db.add(ProjectItem(project_id=p.id,site_code=code,type_5g="New 5G" if p.type=="5g" else None,config=arch,swap_vers_tf="Oui (déjà TF)" if arch=="TF" else "A faire",priorite=s.priorite if s else None,owner=user,updated_by=user))
@app.get("/projects/{pid}/items")
def items(pid:int,db:Session=Depends(get_db),user:str=Depends(current_user)):
    project_or_404(db,pid); return db.scalars(select(ProjectItem).where(ProjectItem.project_id==pid).order_by(ProjectItem.site_code)).all()
@app.post("/projects/{pid}/items")
def add_project_sites(pid:int,body:AddSites,db:Session=Depends(get_db),user:str=Depends(current_user)):
    editor(db,user); p=project_or_404(db,pid); add_items(db,p,body.site_codes,user); db.commit(); return {"ok":True}
@app.put("/projects/{pid}/items/{item_id}")
def change_item(pid:int,item_id:int,body:Change,db:Session=Depends(get_db),user:str=Depends(current_user)):
    editor(db,user); p=project_or_404(db,pid); allowed=ITEM_5G if p.type=="5g" else ITEM_SWAP; bad=set(body.values)-allowed
    if bad: raise HTTPException(400,"Colonne non autorisée")
    if body.values.get("planning") and body.values["planning"] not in MONTHS: raise HTTPException(400,"Planning doit être un mois")
    row=db.get(ProjectItem,item_id)
    if not row or row.project_id!=pid: raise HTTPException(404,"Ligne introuvable")
    result=db.execute(update(ProjectItem).where(ProjectItem.id==item_id,ProjectItem.version==body.expected_version).values(**body.values,version=ProjectItem.version+1,updated_at=datetime.utcnow(),updated_by=user))
    if result.rowcount!=1: db.rollback(); raise HTTPException(409,"Ligne modifiée par un collègue : actualise.")
    db.commit(); return db.get(ProjectItem,item_id)
@app.delete("/projects/{pid}/items/{item_id}")
def delete_item(pid:int,item_id:int,db:Session=Depends(get_db),user:str=Depends(current_user)):
    editor(db,user); row=db.get(ProjectItem,item_id)
    if not row or row.project_id!=pid: raise HTTPException(404,"Ligne introuvable")
    db.delete(row); db.commit(); return {"ok":True}

@app.get("/projects/{pid}/messages")
def messages(pid:int,db:Session=Depends(get_db),user:str=Depends(current_user)):
    project_or_404(db,pid); rows=db.scalars(select(Message).where(Message.project_id==pid).order_by(Message.id)).all(); last=rows[-1].id if rows else 0; read=db.scalar(select(ProjectRead).where(ProjectRead.project_id==pid,ProjectRead.username==user))
    if read: read.last_message_id=last
    else: db.add(ProjectRead(project_id=pid,username=user,last_message_id=last))
    db.commit()
    # Ne jamais renvoyer directement l'objet ORM Message : la pièce jointe
    # binaire n'est pas sérialisable en JSON et masquait tous les champs.
    return [{
        "id": m.id, "project_id": m.project_id, "author": m.author,
        "body": m.body, "sent_at": m.sent_at,
        "attachment_name": m.attachment_name,
        "has_attachment": bool(m.attachment_data),
    } for m in rows]
@app.post("/projects/{pid}/messages")
def send_message(pid:int,body:NewMessage,db:Session=Depends(get_db),user:str=Depends(current_user)):
    project_or_404(db,pid)
    if not body.body.strip() and not body.attach_export: raise HTTPException(400,"Écris un message ou joins l'export")
    data=export_bytes(db,pid) if body.attach_export else None; name=f"projet_{pid}_export.xlsx" if data else None
    db.add(Message(project_id=pid,author=user,body=body.body.strip(),attachment_name=name,attachment_data=data)); db.commit(); return {"ok":True}
@app.post("/projects/{pid}/messages/upload")
async def send_file(pid:int,body:str=Form(""),file:UploadFile|None=File(None),db:Session=Depends(get_db),user:str=Depends(current_user)):
    """Ajoute un fichier quelconque au chat, avec une limite volontaire de 10 Mo."""
    project_or_404(db,pid)
    if not file and not body.strip(): raise HTTPException(400,"Écris un message ou joins un fichier")
    data=None; name=None
    if file:
        data=await file.read()
        if len(data)>10*1024*1024: raise HTTPException(413,"Fichier trop volumineux (10 Mo maximum)")
        name=file.filename or "piece_jointe"
    db.add(Message(project_id=pid,author=user,body=body.strip(),attachment_name=name,attachment_data=data)); db.commit(); return {"ok":True}
@app.get("/messages/{mid}/attachment")
def attachment(mid:int,db:Session=Depends(get_db),user:str=Depends(current_user)):
    m=db.get(Message,mid)
    if not m or not m.attachment_data: raise HTTPException(404,"Pièce jointe introuvable")
    return Response(m.attachment_data,media_type="application/octet-stream",headers={"Content-Disposition":f'attachment; filename="{m.attachment_name}"'})
@app.get("/projects/{pid}/export")
def project_export(pid:int,db:Session=Depends(get_db),user:str=Depends(current_user)):
    return Response(export_bytes(db,pid),media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":f'attachment; filename="project_{pid}.xlsx"'})

@app.get("/reports/bilan-5g.docx")
def bilan_5g_word(db:Session=Depends(get_db),user:str=Depends(current_user)):
    """Bilan Word dynamique : même contenu que l'onglet Bilan, sans TXT."""
    filename=f"bilan_5g_{datetime.now().strftime('%Y-%m-%d')}.docx"
    return Response(
        build_bilan_5g_docx(db),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
