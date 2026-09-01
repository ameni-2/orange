from io import BytesIO
import os
from datetime import date
from html import escape
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
import streamlit.components.v1 as components
try:
    from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode
    HAS_AGGRID=True
except ImportError:
    HAS_AGGRID=False

st.set_page_config(page_title="Orange DRS",page_icon="🟧",layout="wide")
API=os.getenv("DRS_API_URL","http://127.0.0.1:8000")
MONTHS=["Janvier","Février","Mars","Avril","Mai","Juin","Juillet","Août","Septembre","Octobre","Novembre","Décembre"]
FIVE=["site_code","type_5g","config","planning","type_de_site","supports_gc","etat_deploiement","swap_vers_tf","besoin_lld_ip","besoin_wo_radio","besoin_lld_radio","owner","priorite","hw","meteo","kpis","status","statut_ouverture_meteo","plan_action","gc"]
SWAP=["site_code","hw","meteo","plan_action","gc","priorite","besoin_lld_ip","besoin_lld_radio"]
SITE_EDITABLE={"architecture","gouvernorat","delegation","secteur","statut","date_me","latitude","longitude","has_2g","has_3g","has_4g","has_4g_tdd","has_5g","type_transmission","hauteur_gc_m","type_gc","description_gc","cohabitation","sharing","type_site_topo","capacite_mbps","nb_rru","has5g_rru","has_aau","fabricant_ran","oss_group","priorite","nb_secteurs","nb_cells_2g","nb_cells_3g","nb_cells_4g","nb_cells_5g"}
SITE_COLUMNS=["site_code","architecture","gouvernorat","delegation","secteur","statut","date_me","latitude","longitude","has_2g","has_3g","has_4g","has_4g_tdd","has_5g","nb_g900","nb_g1800","nb_u900","nb_u2100","nb_l800","nb_l1800","nb_l2100","nb_ltetdd","nb_nr700","nb_nr1800","nb_nr3500","nb_trx_2g","type_transmission","hauteur_gc_m","type_gc","description_gc","cohabitation","sharing","type_site_topo","capacite_mbps","nb_rru","has5g_rru","has_aau","fabricant_ran","oss_group","priorite","nb_secteurs","nb_cells_2g","nb_cells_3g","nb_cells_4g","nb_cells_5g"]

# En-tête personnalisé : la loupe apparaît uniquement au survol de la colonne.
# Son clic demande le texte recherché et filtre cette colonne sans filtre externe.
if HAS_AGGRID:
  HEADER_SEARCH=JsCode("""
class HeaderSearch {
  init(params) {
    this.params = params;
    this.eGui = document.createElement('div');
    this.eGui.style.cssText = 'display:flex;align-items:center;gap:4px;width:100%;height:100%;overflow:hidden;';
    const title = document.createElement('span');
    title.textContent = params.displayName;
    title.style.cssText = 'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;';
    title.title = 'Cliquer pour trier';
    title.onclick = () => params.progressSort(false);
    const sort = document.createElement('span');
    sort.textContent = '↕';
    sort.style.cssText = 'font-size:11px;opacity:.75;';
    const button = document.createElement('button');
    button.textContent = '⌕';
    button.title = 'Rechercher dans ' + params.displayName;
    button.style.cssText = 'opacity:0;cursor:pointer;border:0;background:transparent;font-size:17px;padding:0 2px;';
    this.eGui.onmouseenter = () => button.style.opacity = '1';
    this.eGui.onmouseleave = () => button.style.opacity = '0';
    button.onclick = (event) => {
      event.stopPropagation();
      document.querySelectorAll('.drs-column-search').forEach(x => x.remove());
      const id = params.column.getColId();
      const model = params.api.getColumnFilterModel(id);
      const popup = document.createElement('div');
      popup.className = 'drs-column-search';
      popup.style.cssText = 'position:fixed;z-index:99999;background:white;border:1px solid #aaa;border-radius:5px;padding:8px;box-shadow:0 3px 12px #777;min-width:220px;';
      const rect = button.getBoundingClientRect(); popup.style.left = rect.left + 'px'; popup.style.top = (rect.bottom + 3) + 'px';
      const input = document.createElement('input'); input.placeholder = 'Rechercher…'; input.value = model && model.filter ? model.filter : ''; input.style.cssText = 'width:100%;box-sizing:border-box;margin-bottom:6px;';
      const select = document.createElement('select'); select.style.cssText = 'width:100%;max-width:230px;';
      const blank = document.createElement('option'); blank.value=''; blank.textContent='Valeurs existantes…'; select.appendChild(blank);
      const values = new Set(); params.api.forEachNode(n => { if (n.data && n.data[id] !== null && n.data[id] !== undefined && n.data[id] !== '') values.add(String(n.data[id])); });
      Array.from(values).sort((a,b) => a.localeCompare(b)).forEach(v => { const o=document.createElement('option'); o.value=v; o.textContent=v; select.appendChild(o); });
      select.onchange = () => { if (select.value) input.value = select.value; };
      const apply = document.createElement('button'); apply.textContent='Appliquer'; apply.style.cssText='margin-top:7px;margin-right:5px;';
      const clear = document.createElement('button'); clear.textContent='Effacer'; clear.style.cssText='margin-top:7px;';
      const applyFilter = () => { const value=input.value.trim(); params.api.setColumnFilterModel(id, value ? {filterType:'text',type:'contains',filter:value} : null); params.api.onFilterChanged(); popup.remove(); };
      apply.onclick=applyFilter; clear.onclick=() => { input.value=''; applyFilter(); }; input.onkeydown=(e)=>{if(e.key==='Enter')applyFilter();};
      popup.append(input,select,apply,clear); document.body.appendChild(popup); input.focus();
    };
    this.eGui.appendChild(title); this.eGui.appendChild(sort); this.eGui.appendChild(button);
  }
  getGui() { return this.eGui; }
}
""")
else:
  HEADER_SEARCH=None

def headers(): return {"Authorization":f"Bearer {st.session_state.get('token','')}"}
def call(method,path,**kwargs):
    r=requests.request(method,API+path,headers=headers(),timeout=30,**kwargs)
    if r.status_code==401: st.session_state.clear(); st.rerun()
    return r
@st.cache_data(ttl=10)
def get(path):
    r=call("GET",path); r.raise_for_status(); return r.json()
def clear(): st.cache_data.clear()
def parse_codes(upload,text):
    codes=[]
    if upload:
        try:
            if upload.name.lower().endswith((".xlsx",".xls")):
                x=pd.read_excel(upload); col=next((c for c in x.columns if str(c).lower() in {"site_code","site","site name","site_name"}),x.columns[0]); codes+=x[col].dropna().astype(str).tolist()
            else: codes+=upload.getvalue().decode("utf-8").replace(",","\n").splitlines()
        except Exception as e: st.error(f"Import impossible : {e}")
    codes+=text.replace(",","\n").splitlines() if text else []
    return list(dict.fromkeys(x.strip() for x in codes if x.strip()))
def read_site_import(upload):
    """Lit le fichier côté navigateur puis transmet les lignes à l'API."""
    if upload.name.lower().endswith((".xlsx", ".xls")):
        frame=pd.read_excel(upload)
    else:
        frame=pd.read_csv(upload)
    frame.columns=[str(c).strip().lower().replace(" ","_").replace("-","_") for c in frame.columns]
    return frame.where(pd.notna(frame),None).to_dict(orient="records")
def orange_report_table(frame, headers):
    """Tableau bilan proche du format e-mail Orange : en-tête jaune et OK vert."""
    head="".join(f"<th>{escape(str(label))}</th>" for label in headers.values())
    rows=[]
    for _, row in frame.iterrows():
        cells=[]
        for field in headers:
            value="" if pd.isna(row.get(field)) else str(row.get(field))
            lower=value.lower()
            css=" report-ok" if lower in {"ok","oui","ouvert sur météo"} or "ouvert" in lower else ""
            cells.append(f"<td class='{css}'>{escape(value)}</td>")
        rows.append("<tr>"+"".join(cells)+"</tr>")
    return """<style>
    .orange-report-wrap{width:100%;overflow-x:auto;padding-bottom:8px;margin:8px 0 18px}
    .orange-report{border-collapse:collapse;min-width:1280px;font-family:Arial,sans-serif;font-size:13px;margin:0}
    .orange-report th{background:#ffc000;border:1px solid #222;padding:7px;text-align:left;white-space:normal}
    .orange-report td{border:1px solid #222;padding:7px;vertical-align:top;white-space:normal;word-break:normal;line-height:1.35}
    .orange-report .report-ok{background:#c6efce;color:#006100;font-weight:600}
    </style><div class='orange-report-wrap'><table class='orange-report'><thead><tr>"""+head+"</tr></thead><tbody>"+"".join(rows)+"</tbody></table></div>"

def show_orange_report(frame, headers):
    """IFrame HTML dédié : les tableaux longs ne sont jamais coupés par Streamlit."""
    height=min(1200,max(185,115+72*max(1,len(frame))))
    components.html(orange_report_table(frame,headers),height=height,scrolling=True)

if "token" not in st.session_state:
    st.title("🟧 Orange DRS")
    st.caption("Connexion à la plateforme interne")
    with st.form("login"):
        user=st.text_input("Identifiant"); password=st.text_input("Mot de passe",type="password")
        if st.form_submit_button("Se connecter"):
            try:
                r=requests.post(API+"/auth/login",json={"username":user,"password":password},timeout=10)
                if r.ok:
                    st.session_state.update(r.json())
                    st.rerun()
                else:
                    st.error("Identifiant ou mot de passe incorrect.")
            except requests.RequestException:
                st.error("Le serveur API n'est pas démarré. Ouvre un deuxième terminal et lance : uvicorn backend.main:app --reload --port 8000")
    st.stop()

projects=get("/projects")
with st.sidebar:
    st.title("🟧 Orange DRS"); st.caption(f"{st.session_state['username']} — {st.session_state['role']}")
    if st.button("Déconnexion"): st.session_state.clear(); st.rerun()
    page=st.radio("Navigation",["Données", "Nouveau projet", "Projets", "Bilan global"])

if page=="Données":
    st.title("Données réseau")
    df=pd.DataFrame(get("/sites"))
    # L'ordre est volontairement identique à celui du tableau demandé, sans répétition.
    view=df[["id","version"]+[c for c in SITE_COLUMNS if c in df.columns]].copy()
    # Colonne technique visible uniquement pour contenir les cases à cocher.
    # Elle doit être la première colonne : AgGrid y attache la sélection.
    view.insert(0,"sélection","")
    if HAS_AGGRID:
        gb=GridOptionsBuilder.from_dataframe(view)
        # Le menu/funnel de filtre apparaît au survol de chaque en-tête de colonne.
        # Il permet de saisir le critère directement pour la colonne concernée.
        gb.configure_default_column(sortable=True,resizable=True,filter=True,floatingFilter=False,editable=False,minWidth=105)
        preselected=view.index[view.site_code.isin(st.session_state.get("selected",[]))].tolist()
        gb.configure_selection("multiple",use_checkbox=True,header_checkbox=True,pre_selected_rows=preselected)
        gb.configure_column("sélection",header_name="",width=52,pinned="left",editable=False,filter=False,sortable=False)
        gb.configure_column("id",hide=True); gb.configure_column("version",hide=True); gb.configure_column("site_code",pinned="left",editable=False,width=125)
        for col in SITE_COLUMNS:
            if col in view.columns:
                gb.configure_column(col,headerComponent=HEADER_SEARCH,filter="agTextColumnFilter")
        for col in SITE_EDITABLE:
            if col in view.columns: gb.configure_column(col,editable=True)
        response=AgGrid(
            view, gridOptions=gb.build(), update_mode=GridUpdateMode.MODEL_CHANGED,
            data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
            fit_columns_on_grid_load=False, height=520, theme="balham", key="main_grid",
            # Barre intégrée : recherche rapide + téléchargement. Les menus
            # de colonnes permettent ensuite de filtrer/masquer une colonne.
            show_toolbar=True, show_search=True, show_download_button=True,
            update_on=["cellValueChanged", "selectionChanged", "filterChanged", "sortChanged"],
            allow_unsafe_jscode=True,
        )
        edited=pd.DataFrame(response["data"])
        picked=response.selected_rows if response.selected_rows is not None else pd.DataFrame()
    else:
        view["sélection"]=view.site_code.isin(st.session_state.get("selected",[]))
        edited=st.data_editor(view,hide_index=True,use_container_width=True,disabled=[c for c in view.columns if c not in SITE_EDITABLE|{"sélection"}])
        picked=edited.loc[edited["sélection"]]
    st.session_state["selected"]=picked.site_code.tolist() if not picked.empty else []
    st.caption(f"{len(edited)} sites affichés — {len(st.session_state['selected'])} sélectionnés pour un projet.")
    if st.button("Enregistrer les modifications des sites"):
        conflicts=[]
        for _,old in view.iterrows():
            new=edited.loc[edited.id==old.id].iloc[0]; values={}
            for col in SITE_EDITABLE:
                if col not in new: continue
                before,after=old[col],new[col]
                if (pd.isna(before) and pd.isna(after)) or str(before)==str(after): continue
                values[col]=None if pd.isna(after) else after
            if values:
                r=call("PUT",f"/sites/{int(old.id)}",json={"expected_version":int(old.version),"values":values})
                if not r.ok: conflicts.append(f"{old.site_code}: {r.json().get('detail',r.text)}")
        clear()
        if conflicts:
            st.error(" | ".join(conflicts))
        else:
            st.success("Données mises à jour immédiatement.")
    # Comportement attendu : sélection => export ciblé ; aucune sélection => toute la vue.
    export_df=edited[edited.site_code.isin(st.session_state["selected"])] if st.session_state["selected"] else edited
    out=BytesIO(); export_df.drop(columns=["id","version","sélection"],errors="ignore").to_excel(out,index=False,engine="openpyxl")
    export_label="Exporter les sites sélectionnés" if st.session_state["selected"] else "Exporter tous les sites affichés"
    st.download_button(export_label,out.getvalue(),"sites_export.xlsx",disabled=export_df.empty)
    if st.button("Créer un nouveau projet avec la sélection",disabled=not st.session_state["selected"],type="primary"):
        st.session_state["project_codes"]=st.session_state["selected"]; st.rerun()
    with st.expander("Ajouter des sites à la base"):
        source=st.radio("Méthode",["Importer Excel / CSV", "Saisie manuelle"],horizontal=True,key="site_source")
        if source=="Importer Excel / CSV":
            site_file=st.file_uploader("Fichier contenant les colonnes de la base",type=["xlsx","xls","csv"],key="site_upload")
            if st.button("Importer les sites",disabled=site_file is None):
                try:
                    r=call("POST","/sites/import",json={"records":read_site_import(site_file)})
                    if r.ok:
                        result=r.json(); clear(); st.success(f"{len(result['created'])} site(s) ajouté(s).")
                        if result["duplicates"]: st.warning("Déjà présents : " + ", ".join(result["duplicates"]))
                        if result["errors"]: st.error(" | ".join(result["errors"]))
                    else: st.error(r.json().get("detail",r.text))
                except Exception as exc: st.error(f"Import impossible : {exc}")
        else:
            with st.form("manual_site"):
                a,b,c,d=st.columns(4)
                code=a.text_input("Site code *",placeholder="ARI_0092")
                gov=b.text_input("Gouvernorat *",placeholder="Ariana")
                deleg=c.text_input("Délégation *",placeholder="Raoued")
                sector=d.text_input("Secteur *")
                e,f,g,h=st.columns(4)
                architecture=e.selectbox("Architecture",["","TF","BH","FO"])
                statut=f.selectbox("Statut",["Actif","Inactif"])
                has5g=g.selectbox("5G",["✗","✓"])
                priority=h.selectbox("Priorité",["","P0","P1","P2","P3"])
                submit=st.form_submit_button("Ajouter le site")
            if submit:
                payload={"site_code":code,"gouvernorat":gov,"delegation":deleg,"secteur":sector,"architecture":architecture,"statut":statut,"has_5g":has5g,"priorite":priority}
                r=call("POST","/sites",json={"values":payload})
                if r.ok: clear(); st.success("Site ajouté.")
                else: st.error(r.json().get("detail",r.text))
    if st.session_state["selected"]:
        if st.button("🗑️ Supprimer les sites sélectionnés",type="secondary"):
            st.session_state["confirm_delete_sites"]=True
        if st.session_state.get("confirm_delete_sites"):
            st.warning(f"Confirmer la suppression définitive de {len(st.session_state['selected'])} site(s) ? Les données principales seront supprimées.")
            d1,d2=st.columns(2)
            if d1.button("Oui, supprimer définitivement",type="primary"):
                ids=edited.loc[edited.site_code.isin(st.session_state["selected"]),"id"].astype(int).tolist()
                r=call("DELETE","/sites",json={"ids":ids})
                if r.ok:
                    st.session_state["selected"]=[]; st.session_state["confirm_delete_sites"]=False; clear(); st.success("Sites supprimés.")
                else: st.error(r.json().get("detail",r.text))
            if d2.button("Annuler la suppression"):
                st.session_state["confirm_delete_sites"]=False; st.rerun()

elif page=="Nouveau projet":
    st.title("Nouveau projet")
    st.caption("Projet vivant : les sites et les cellules restent modifiables après création.")
    selected=st.session_state.pop("project_codes",st.session_state.get("selected",[]))
    c1,c2,c3=st.columns(3); name=c1.text_input("Nom du projet"); typ=c2.selectbox("Type",["5g","swap"],format_func=lambda x:"New 5G" if x=="5g" else "Swap vers MM"); objectif=c3.number_input("Objectif (sites)",min_value=0,value=len(selected),step=1)
    upload=st.file_uploader("Importer une liste de sites (.xlsx, .txt, .csv)",type=["xlsx","xls","txt","csv"])
    pasted=st.text_area("Ou coller les sites (un par ligne ou séparés par virgule)")
    imported=parse_codes(upload,pasted); all_codes=list(dict.fromkeys(selected+imported))
    st.write("Sites qui seront ajoutés :", ", ".join(all_codes) if all_codes else "aucun")
    if st.button("Créer le projet",type="primary"):
        r=call("POST","/projects",json={"name":name,"type":typ,"site_codes":all_codes,"objectif":objectif})
        if r.ok: clear(); st.session_state["open_project"]=r.json()["id"]; st.success("Projet créé avec le message et l'export initial dans son chat.")
        else: st.error(r.json().get("detail",r.text))

elif page=="Projets":
    st.title("Projets")
    if not projects: st.info("Aucun projet."); st.stop()
    labels={f"{p['name']} · {p['type'].upper()} {'🔴 '+str(p['unread']) if p['unread'] else ''}":p["id"] for p in projects}
    default=next((i for i,v in enumerate(labels.values()) if v==st.session_state.get("open_project")),0)
    pid=st.selectbox("Ouvrir un projet",list(labels.values()),index=default,format_func=lambda x:next(k for k,v in labels.items() if v==x)); p=next(x for x in projects if x["id"]==pid)
    tab_suivi,tab_chat,tab_bilan=st.tabs(["Suivi du projet", "💬 Chat", "Bilan"])
    with tab_suivi:
        items=pd.DataFrame(get(f"/projects/{pid}/items")); cols=FIVE if p["type"]=="5g" else SWAP
        st.subheader(p["name"])
        if items.empty: items=pd.DataFrame(columns=["id","version"]+cols)
        table=items[[c for c in ["id","version"]+cols if c in items.columns]].copy()
        # Même grille que la page Données : tri, loupe au survol des en-têtes
        # et filtres par colonne. id/version restent nécessaires au backend
        # mais sont invisibles pour les utilisateurs.
        if HAS_AGGRID:
            pg=GridOptionsBuilder.from_dataframe(table)
            pg.configure_default_column(sortable=True,resizable=True,filter=True,floatingFilter=False,editable=True,minWidth=120)
            pg.configure_column("id",hide=True,editable=False)
            pg.configure_column("version",hide=True,editable=False)
            pg.configure_column("site_code",editable=False,pinned="left",width=130)
            for col in cols:
                if col in table.columns:
                    pg.configure_column(col,headerComponent=HEADER_SEARCH,filter="agTextColumnFilter",editable=col!="site_code")
            if "planning" in table.columns:
                pg.configure_column("planning",cellEditor="agSelectCellEditor",cellEditorParams={"values":MONTHS},headerComponent=HEADER_SEARCH)
            project_grid=AgGrid(table,gridOptions=pg.build(),update_mode=GridUpdateMode.MODEL_CHANGED,data_return_mode=DataReturnMode.FILTERED_AND_SORTED,fit_columns_on_grid_load=False,height=430,theme="balham",key=f"project_{pid}",show_toolbar=True,show_search=True,show_download_button=True,update_on=["cellValueChanged","filterChanged","sortChanged"],allow_unsafe_jscode=True)
            changed=pd.DataFrame(project_grid["data"])
        else:
            changed=st.data_editor(table,hide_index=True,use_container_width=True,disabled=["id","version"],column_config={"id":None,"version":None,"planning":st.column_config.SelectboxColumn("planning",options=MONTHS)},key=f"project_{pid}")
        if st.button("Enregistrer les modifications"):
            errors=[]
            for _,old in table.iterrows():
                new=changed.loc[changed.id==old.id].iloc[0]; values={c:new[c] for c in cols if c in new and str(new[c])!=str(old.get(c))}
                if values:
                    r=call("PUT",f"/projects/{pid}/items/{int(old.id)}",json={"expected_version":int(old.version),"values":values})
                    if not r.ok: errors.append(f"{old.site_code}: {r.json().get('detail')}")
            clear()
            if errors:
                st.error(" | ".join(errors))
            else:
                st.success("Modifications enregistrées.")
        add=st.text_input("Ajouter des sites à ce projet (codes séparés par virgule)")
        a1,a2=st.columns(2)
        if a1.button("Ajouter les sites"):
            r=call("POST",f"/projects/{pid}/items",json={"site_codes":parse_codes(None,add)})
            clear()
            if r.ok:
                st.success("Sites ajoutés.")
            else:
                st.error(r.text)
        if not items.empty:
            remove=a2.multiselect("Retirer des sites du projet",items.site_code.tolist())
            if st.button("Retirer la sélection"):
                for code in remove: call("DELETE",f"/projects/{pid}/items/{int(items.loc[items.site_code==code,'id'].iloc[0])}")
                clear(); st.rerun()
        r=call("GET",f"/projects/{pid}/export"); st.download_button("Exporter le tableau projet",r.content,f"{p['name']}.xlsx")
    with tab_chat:
        st.subheader("Conversation du projet")
        messages=get(f"/projects/{pid}/messages")
        for m in messages:
            with st.chat_message("assistant" if m["author"]=="Système" else "user"):
                st.write(f"**{m['author']}** · {m['sent_at']}"); st.write(m["body"])
                if m.get("attachment_name"):
                    data=call("GET",f"/messages/{m['id']}/attachment").content; st.download_button("Télécharger " + m["attachment_name"],data,m["attachment_name"],key=f"att{m['id']}")
        with st.form(f"chat{pid}"):
            body=st.text_area("Message"); attach=st.checkbox("Joindre l'export Excel actuel du projet")
            chat_file=st.file_uploader("Joindre un fichier",key=f"chatfile{pid}")
            if st.form_submit_button("Envoyer"):
                if chat_file:
                    r=call("POST",f"/projects/{pid}/messages/upload",data={"body":body},files={"file":(chat_file.name,chat_file.getvalue(),chat_file.type or "application/octet-stream")})
                else:
                    r=call("POST",f"/projects/{pid}/messages",json={"body":body,"attach_export":attach})
                clear()
                if r.ok: st.rerun()
                else: st.error(r.text)
    with tab_bilan:
        if items.empty: st.info("Ajoute des sites pour afficher le bilan.")
        else:
            state="etat_deploiement" if p["type"]=="5g" else "gc"; done=int(items[state].isin(["OK","Terminé","Oui"]).sum()); objective=max(int(p.get("objectif") or 0),1)
            c1,c2,c3,c4=st.columns(4); c1.metric("Sites du projet",len(items)); c2.metric("Terminés",done); c3.metric("Objectif",objective); c4.metric("Avancement vs objectif",f"{100*done/objective:.1f}%")
            left,right=st.columns(2)
            with left:
                progress=pd.DataFrame({"État":["Atteint","Reste à atteindre"],"Sites":[min(done,objective),max(objective-done,0)]})
                st.plotly_chart(px.pie(progress,names="État",values="Sites",hole=.68,color="État",color_discrete_map={"Atteint":"#2E7D32","Reste à atteindre":"#E0E0E0"},title="Avancement versus objectif"),use_container_width=True)
            with right:
                states=items.groupby(state,dropna=False).size().reset_index(name="Sites")
                st.plotly_chart(px.bar(states,x=state,y="Sites",color=state,text="Sites",title="État opérationnel des sites"),use_container_width=True)
            if "planning" in items.columns:
                monthly=items.groupby("planning",dropna=False).size().reindex(MONTHS,fill_value=0).reset_index(name="Sites"); monthly.columns=["Mois","Sites"]; st.plotly_chart(px.line(monthly,x="Mois",y="Sites",markers=True,title="Charge planifiée par mois"),use_container_width=True)
            choices=[x for x in ["meteo","swap_vers_tf","priorite","owner","type_5g","config","besoin_lld_ip","besoin_lld_radio"] if x in items.columns]
            if choices:
                field=st.selectbox("Analyse complémentaire",choices,key=f"dash_{pid}")
                detail=items.groupby(field,dropna=False).size().reset_index(name="Sites")
                st.plotly_chart(px.bar(detail,x=field,y="Sites",color=field,text="Sites",title=f"Analyse par {field.replace('_',' ')}"),use_container_width=True)

else:
    st.title("Bilan global")
    df=pd.DataFrame(get("/sites")); total=len(df); active=int((df.statut=="Actif").sum()); five=int((df.has_5g=="✓").sum()); tf=int((df.architecture=="TF").sum()); rru=int((df.has5g_rru=="✓").sum()); aau=int((df.has_aau=="✓").sum())
    c1,c2,c3,c4,c5,c6=st.columns(6); c1.metric("Sites",total); c2.metric("Actifs",active); c3.metric("5G",five); c4.metric("Déjà TF",tf); c5.metric("5G RRU",rru); c6.metric("AAU",aau)
    all_items=[]
    for project in projects:
        project_items=pd.DataFrame(get(f"/projects/{project['id']}/items"));
        if not project_items.empty: project_items["projet"]=project["name"]; project_items["objectif_projet"]=project.get("objectif",0); all_items.append(project_items)
    g1,g2=st.columns(2)
    with g1:
        readiness=pd.DataFrame({"Indicateur":["5G active","Pas encore 5G","Déjà TF","Autres architectures"],"Sites":[five,total-five,tf,total-tf]})
        st.plotly_chart(px.bar(readiness,x="Indicateur",y="Sites",color="Indicateur",text="Sites",title="Maturité 5G et transmission",color_discrete_sequence=["#F57C00","#BDBDBD","#2E7D32","#90A4AE"]),use_container_width=True)
    with g2:
        activity=df.groupby(["gouvernorat","statut"],dropna=False).size().reset_index(name="Sites")
        st.plotly_chart(px.bar(activity,x="gouvernorat",y="Sites",color="statut",barmode="stack",text="Sites",title="Sites actifs / inactifs par gouvernorat",color_discrete_map={"Actif":"#2E7D32","Inactif":"#C62828"}),use_container_width=True)
    dimensions=[x for x in ["gouvernorat","architecture","priorite","type_transmission","fabricant_ran","has_5g","has5g_rru","has_aau"] if x in df.columns]
    dimension=st.selectbox("Analyse détaillée",dimensions,format_func=lambda x:x.replace("_"," "))
    detail=df.groupby(dimension,dropna=False).size().reset_index(name="Sites")
    st.plotly_chart(px.bar(detail,x=dimension,y="Sites",color=dimension,text="Sites",title=f"Répartition des sites par {dimension.replace('_',' ')}"),use_container_width=True)
    if all_items:
        st.subheader("Objectifs et avancement des projets")
        rows=[]
        for project in projects:
            its=pd.DataFrame(get(f"/projects/{project['id']}/items")); state="etat_deploiement" if project["type"]=="5g" else "gc"; done=int(its[state].isin(["OK","Terminé","Oui"]).sum()) if state in its else 0; rows.append({"Projet":project["name"],"Objectif":project.get("objectif",0),"Atteint":done})
        prog=pd.DataFrame(rows); st.plotly_chart(px.bar(prog.melt(id_vars="Projet",value_vars=["Objectif","Atteint"],var_name="Mesure",value_name="Sites"),x="Projet",y="Sites",color="Mesure",barmode="group",text="Sites",title="Atteint vs objectif par projet",color_discrete_map={"Objectif":"#90A4AE","Atteint":"#2E7D32"}),use_container_width=True)

        # Bilan quotidien exportable : format fidèle au bilan e-mail fourni.
        track=pd.concat(all_items,ignore_index=True)
        meteo_status=track.get("statut_ouverture_meteo",track.get("meteo",pd.Series(dtype=str))).fillna("").astype(str)
        open_meteo=track[meteo_status.str.contains("ouvert|open",case=False,regex=True)].copy()
        not_open_meteo=track[~meteo_status.str.contains("ouvert|open",case=False,regex=True)].copy()
        swapped=track.get("swap_vers_tf",pd.Series(dtype=str)).fillna("").astype(str).str.contains("oui|tf",case=False,regex=True).sum()
        st.divider()
        today=date.today()
        st.markdown("<mark>Bilan 5G :</mark>",unsafe_allow_html=True)
        st.write(f"Veuillez trouver ci-après l’état d’avancement des activations NR 5G jusqu’au **{today.strftime('%d/%m')}**.")
        st.markdown("**Bilan 5G :**")
        st.markdown(f"- Sites swappés : **{int(swapped)}**  \n- Sites activés : **{five}**  \n- Sites ouverts sur météo : **{len(open_meteo)}**")
        month_name=MONTHS[today.month-1]
        st.markdown(f"<u><b>État d’avancement au mois de {month_name}</b></u> : <span style='color:#00a651;font-weight:700'>{len(open_meteo)} sites ouverts sur météo</span>",unsafe_allow_html=True)
        report_rows=[]
        for project in projects:
            its=track[track["projet"]==project["name"]].copy()
            if its.empty: continue
            actions=its.get("type_5g",pd.Series("",index=its.index)).fillna("")
            action_values=[a for a in actions.unique() if a] or ["New 5G" if project["type"]=="5g" else "Swap vers MM"]
            for action in action_values:
                group=its[actions==action] if (actions==action).any() else its
                objective=int(project.get("objectif") or len(group))
                swap_done=int(group.get("swap_vers_tf",pd.Series(dtype=str)).fillna("").astype(str).str.contains("oui|tf",case=False,regex=True).sum())
                state="etat_deploiement" if project["type"]=="5g" else "gc"
                activated=int(group.get(state,pd.Series(dtype=str)).fillna("").isin(["OK","Terminé","Oui"]).sum())
                opened=int(group.index.isin(open_meteo.index).sum())
                note=next((str(x) for x in group.get("plan_action",pd.Series(dtype=str)).dropna() if str(x).strip()), "Objectif atteint ou suivi quotidien requis" if opened>=objective else f"Reste {max(objective-opened,0)} site(s) à traiter")
                report_rows.append({"Projet":project["name"],"Type d’action":action,"Objectif":objective,"Swap done":swap_done,"Sites activés":activated,"Sites ouverts sur météo":opened,"% avancement":f"{round(100*opened/objective,1) if objective else 0}%","Point d’attention & Next step":note})
        report=pd.DataFrame(report_rows)
        show_orange_report(report,{"Projet":"", "Type d’action":"Type d’action", "Objectif":"Objectif", "Swap done":"Swap done", "Sites activés":"Sites activés", "Sites ouverts sur météo":"Sites ouverts sur météo", "% avancement":f"% avancement au {today.strftime('%d/%m')}", "Point d’attention & Next step":"Point d’attention & Next step"})
        st.markdown("- **<u>Sites ouverts sur météo</u>** (confirmer la résolution de pb) :",unsafe_allow_html=True)
        if open_meteo.empty:
            empty_open=pd.DataFrame(columns=["site_code","config","État HW","État activation","KPIs","Status","Statut ouverture sur météo","owner"])
            show_orange_report(empty_open,{"site_code":"Site Name","config":"Config Site","État HW":"État HW","État activation":"État d’activation","KPIs":"KPIs","Status":"Status","Statut ouverture sur météo":"Status ouverture sur météo","owner":"Owner"})
        else:
            open_view=open_meteo.copy()
            open_view["Statut ouverture sur météo"]=open_view.get("statut_ouverture_meteo",open_view.get("meteo","")).fillna("Ouvert sur météo")
            open_view["État activation"]=open_view.get("etat_deploiement","")
            open_view["État HW"]=open_view.get("hw","")
            open_view["KPIs"]=open_view.get("kpis","")
            open_view["Status"]=open_view.get("status",open_view.get("plan_action","")).fillna("")
            show_orange_report(open_view,{"site_code":"Site Name","config":"Config Site","État HW":"État HW","État activation":"État d’activation","KPIs":"KPIs","Status":"Status","Statut ouverture sur météo":"Status ouverture sur météo","owner":"Owner"})
        st.markdown("- **<u>Sites non ouverts sur météo</u>** (reliquat du mois précédent à inclure dans le plan du mois suivant) :",unsafe_allow_html=True)
        if not_open_meteo.empty:
            closed_view=not_open_meteo.copy()
            closed_view["État HW"]=closed_view.get("hw",""); closed_view["État activation"]=closed_view.get("etat_deploiement",""); closed_view["État KPIs"]=closed_view.get("kpis",""); closed_view["Status"]=closed_view.get("status",closed_view.get("plan_action","")).fillna("")
            show_orange_report(closed_view,{"site_code":"Site Name","config":"Config site","État HW":"État HW","État activation":"État activation","État KPIs":"État KPIs","Status":"Status"})
        else:
            empty_closed=pd.DataFrame(columns=["site_code","config","État HW","État activation","État KPIs","Status"])
            show_orange_report(empty_closed,{"site_code":"Site Name","config":"Config site","État HW":"État HW","État activation":"État activation","État KPIs":"État KPIs","Status":"Status"})
        word_response=call("GET", "/reports/bilan-5g.docx")
        if word_response.ok:
            st.download_button(
                "Exporter le bilan Word",
                data=word_response.content,
                file_name=f"bilan_5g_{date.today().isoformat()}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        else:
            st.error("Le bilan Word n'a pas pu être généré. Vérifie que le backend a été redémarré.")
