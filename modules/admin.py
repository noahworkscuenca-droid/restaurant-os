import os
import streamlit as st

PLAN_ORDER = ["free", "basico", "profesional", "enterprise"]
PLAN_LABELS = {
    "free":        "U0001F193 Gratuito",
    "basico":      "⭐ Básico",
    "profesional": "U0001F48E Profesional",
    "enterprise":  "U0001F3C6 Enterprise",
}


def _admin_client():
    """Supabase client con service_role key — bypasses RLS."""
    try:
        from supabase import create_client
        url = os.getenv("SUPABASE_URL")         or st.secrets.get("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_SERVICE_KEY") or st.secrets.get("SUPABASE_SERVICE_KEY", "")
        if url and key:
            return create_client(url, key)
    except Exception as e:
        st.error(f"Error al conectar admin: {e}")
    return None


def render_admin_page():
    st.title("U0001F527 Panel de Administración")
    st.caption("Solo visible para administradores.")

    sb = _admin_client()
    if not sb:
        st.error("Se necesita SUPABASE_SERVICE_KEY en los Streamlit Secrets.")
        return

    tab_users, tab_manual, tab_stats = st.tabs(["Usuarios", "Cambio rápido", "Estadísticas"])

    with tab_users:
        st.subheader("Todos los usuarios")
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            search = st.text_input("U0001F50D Buscar", placeholder="email o nombre", label_visibility="collapsed")
        with c2:
            filter_plan = st.selectbox("Plan", ["Todos"] + PLAN_ORDER, format_func=lambda x: PLAN_LABELS.get(x, x), label_visibility="collapsed")
        with c3:
            if st.button("U0001F504 Recargar", use_container_width=True):
                st.rerun()

        try:
            query = sb.table("profiles").select("id, email, full_name, plan, stripe_customer_id, is_admin, created_at")
            if filter_plan != "Todos":
                query = query.eq("plan", filter_plan)
            res      = query.order("created_at", desc=True).execute()
            profiles = res.data or []
        except Exception as e:
            st.error(f"Error al cargar usuarios: {e}")
            profiles = []

        if search:
            q = search.lower()
            profiles = [p for p in profiles if q in (p.get("email") or "").lower() or q in (p.get("full_name") or "").lower()]

        m = st.columns(5)
        m[0].metric("Total", len(profiles))
        for i, pk in enumerate(["free", "basico", "profesional", "enterprise"]):
            m[i + 1].metric(PLAN_LABELS[pk], sum(1 for p in profiles if p.get("plan") == pk))

        st.divider()

        if not profiles:
            st.info("No se encontraron usuarios.")
        else:
            for p in profiles:
                uid    = p.get("id", "")
                email  = p.get("email") or "—"
                name   = p.get("full_name") or email.split("@")[0].capitalize()
                plan   = p.get("plan", "free")
                stripe = p.get("stripe_customer_id") or "—"
                joined = (p.get("created_at") or "")[:10]
                is_adm = p.get("is_admin", False)

                with st.expander(f"{PLAN_LABELS.get(plan, plan)}  ·  **{name}**  ·  {email}"):
                    col_info, col_plan, col_action = st.columns([3, 1, 1])
                    with col_info:
                        st.markdown(f"**Email:** {email}  \n**Stripe ID:** `{stripe}`  \n**Registro:** {joined}")
                    with col_plan:
                        new_plan = st.selectbox("Plan", PLAN_ORDER, index=PLAN_ORDER.index(plan), format_func=lambda x: PLAN_LABELS[x], key=f"plan_sel_{uid}")
                        new_admin = st.checkbox("Admin", value=is_adm, key=f"adm_{uid}")
                    with col_action:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("U0001F4BE Guardar", key=f"save_{uid}", use_container_width=True):
                            try:
                                sb.table("profiles").update({"plan": new_plan, "is_admin": new_admin}).eq("id", uid).execute()
                                st.success(f"✅ Actualizado → {PLAN_LABELS[new_plan]}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

    with tab_manual:
        st.subheader("Cambio rápido por email")
        st.markdown("Asigna un plan manualmente sin pasar por Stripe. Útil para cortenías y correcciones.")
        with st.form("manual_form", border=True):
            target_email = st.text_input("U0001F4E7 Email del usuario")
            new_plan     = st.selectbox("Nuevo plan", PLAN_ORDER, format_func=lambda x: PLAN_LABELS[x], index=1)
            make_admin   = st.checkbox("También dar permisos de Admin")
            st.text_input("Motivo (referencia interna)", placeholder="Cortesía, error de pago, beta tester…")
            submitted = st.form_submit_button("✅ Aplicar cambio", type="primary")
            if submitted:
                if not target_email:
                    st.warning("Iadmin.pyngresa un email.")
                else:
                    try:
                        res = sb.table("profiles").select("id, full_name").eq("email", target_email).single().execute()
                        if res.data:
                            update = {"plan": new_plan}
                            if make_admin:
                                update["is_admin"] = True
                            sb.table("profiles").update(update).eq("email", target_email).execute()
                            display = res.data.get("full_name") or target_email
                            st.success(f"✅ {display} → {PLAN_LABELS[new_plan]}" + (" + Admin" if make_admin else ""))
                        else:
                            st.warning("No se encontró ningún usuario con ese email.")
                    except Exception as e:
                        st.error(f"Error: {e}")

    with tab_stats:
        st.subheader("Distribución de planes")
        try:
            all_res  = sb.table("profiles").select("plan, created_at").execute()
            all_data = all_res.data or []
            import pandas as pd
            df = pd.DataFrame(all_data)
            if not df.empty:
                plan_counts = df["plan"].value_counts().reset_index()
                plan_counts.columns = ["Plan", "Usuarios"]
                plan_counts["Plan"] = plan_counts["Plan"].map(PLAN_LABELS)
                st.bar_chart(plan_counts.set_index("Plan"))
                st.divider()
                st.subheader("Crecimiento de registros")
                df["created_at"] = pd.to_datetime(df["created_at"]).dt.date
                growth = df.groupby("created_at").size().reset_index(name="Nuevos usuarios")
                st.line_chart(growth.set_index("created_at"))
            else:
                st.info("Sin datos aún.")
        except Exception as e:
            st.error(f"Error al cargar estadísticas: {e}")
