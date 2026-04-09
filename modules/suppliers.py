"""
modules/suppliers.py — Gestión de proveedores y sistema de alias OCR
"""

import streamlit as st
from modules.database import get_supabase_client


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_supplier_alias_map() -> dict:
    """
    Retorna un diccionario {alias_lower: nombre_canonico} para que el OCR
    pueda normalizar nombres de proveedores automáticamente.
    Ejemplo: {"distribuidora granjero": "Don Pepe", "dist. granjero": "Don Pepe"}
    """
    db = get_supabase_client()
    result = db.table("suppliers").select("name, aliases").eq("is_active", True).execute()
    alias_map = {}
    for row in (result.data or []):
        canonical = row.get("name", "").strip()
        aliases_raw = row.get("aliases", "") or ""
        for alias in aliases_raw.split(","):
            alias = alias.strip()
            if alias:
                alias_map[alias.lower()] = canonical
    return alias_map


def resolve_supplier_name(raw_name: str) -> str:
    """
    Dado un nombre como lo leyó Gemini, retorna el nombre canónico si hay
    un alias que coincida, o el nombre original si no hay match.
    """
    if not raw_name:
        return raw_name
    alias_map = get_supplier_alias_map()
    return alias_map.get(raw_name.strip().lower(), raw_name.strip())


# ── Página Streamlit ──────────────────────────────────────────────────────────

def render_suppliers_page():
    db = get_supabase_client()

    st.markdown("## 🤝 Proveedores & Alias")
    st.caption(
        "Registra los nombres exactos que aparecen en las facturas como alias. "
        "Cuando Gemini lea un alias, lo traducirá automáticamente al nombre interno."
    )

    st.divider()

    # ── Formulario: Nuevo proveedor ───────────────────────────────────────────
    with st.expander("➕ Añadir nuevo proveedor", expanded=False):
        with st.form("form_nuevo_proveedor", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nombre  = c1.text_input("Nombre interno", placeholder="Ej: Don Pepe")
            aliases = c2.text_input(
                "Alias en facturas (separados por coma)",
                placeholder="Ej: DISTRIBUIDORA GRANJERO, DIST. GRANJERO S.A.",
            )
            col_extra = st.columns(3)
            ruc   = col_extra[0].text_input("RUC / NIT (opcional)")
            email = col_extra[1].text_input("Email (opcional)")
            phone = col_extra[2].text_input("Teléfono (opcional)")

            if st.form_submit_button("💾 Guardar proveedor", type="primary"):
                if nombre.strip():
                    db.table("suppliers").insert({
                        "name":    nombre.strip(),
                        "aliases": aliases.strip(),
                        "ruc_nit": ruc.strip() or None,
                        "email":   email.strip() or None,
                        "phone":   phone.strip() or None,
                    }).execute()
                    st.success(f"✅ Proveedor **{nombre}** registrado.")
                    st.rerun()
                else:
                    st.warning("El nombre interno es obligatorio.")

    # ── Listado de proveedores ────────────────────────────────────────────────
    result = db.table("suppliers").select("*").eq("is_active", True).order("name").execute()
    proveedores = result.data or []

    if not proveedores:
        st.info("Aún no tienes proveedores. Usa el formulario de arriba para añadir el primero.")
        return

    st.markdown(
        f"<p style='font-size:0.8rem;font-weight:700;color:#64748B;"
        f"text-transform:uppercase;letter-spacing:0.07em;margin-bottom:0.5rem;'>"
        f"Directorio — {len(proveedores)} proveedores activos</p>",
        unsafe_allow_html=True,
    )

    for prov in proveedores:
        prov_id  = prov["id"]
        nombre   = prov.get("name", "")
        aliases  = prov.get("aliases", "") or ""

        with st.container():
            col_info, col_alias, col_actions = st.columns([2, 4, 1])

            with col_info:
                st.markdown(f"**{nombre}**")
                if prov.get("phone"):
                    st.caption(f"📞 {prov['phone']}")

            with col_alias:
                # Editor de alias inline
                alias_key = f"alias_edit_{prov_id}"
                nuevo_alias = st.text_input(
                    "Alias (separados por coma)",
                    value=aliases,
                    key=alias_key,
                    label_visibility="collapsed",
                    placeholder="Ej: NOMBRE EN FACTURA, OTRO NOMBRE...",
                )
                if nuevo_alias != aliases:
                    if st.button("💾 Guardar alias", key=f"save_alias_{prov_id}"):
                        db.table("suppliers").update({"aliases": nuevo_alias.strip()}).eq("id", prov_id).execute()
                        st.toast(f"Alias de {nombre} actualizados.", icon="✅")
                        st.rerun()

            with col_actions:
                confirm_key = f"confirm_del_sup_{prov_id}"
                if not st.session_state.get(confirm_key):
                    if st.button("🗑️", key=f"del_sup_{prov_id}", help="Eliminar proveedor"):
                        st.session_state[confirm_key] = True
                        st.rerun()
                else:
                    if st.button("⚠️ Confirmar", key=f"confirm_sup_{prov_id}", type="primary"):
                        db.table("suppliers").update({"is_active": False}).eq("id", prov_id).execute()
                        st.session_state.pop(confirm_key, None)
                        st.toast(f"{nombre} desactivado.", icon="🗑️")
                        st.rerun()
                    if st.button("✖", key=f"cancel_sup_{prov_id}"):
                        st.session_state.pop(confirm_key, None)
                        st.rerun()

            st.divider()
