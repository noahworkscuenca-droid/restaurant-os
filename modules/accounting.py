"""
modules/accounting.py — Páginas de contabilidad y cuentas por pagar
"""

from datetime import date, datetime
from typing import Optional

import pandas as pd
import streamlit as st

from modules.database import get_supabase_client


# ── Página: Lista de Facturas ────────────────────────────────────────────────

def render_accounting_page():
    """Vista principal del archivo contable con filtros por Año/Mes/Categoría."""

    db = get_supabase_client()
    st.title("🧾 Facturas")

    # ── Barra de búsqueda rápida ─────────────────────────────────────────────
    search_text = st.text_input(
        "🔍 Buscar por proveedor o número de factura",
        placeholder="Ej: Don Pepe o F-1029",
        label_visibility="visible",
    )

    # ── Filtros ──────────────────────────────────────────────────────────────
    with st.expander("🔍 Filtros avanzados", expanded=False):
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            current_year = date.today().year
            year_options = list(range(current_year, current_year - 5, -1))
            selected_year = st.selectbox("Año", year_options, index=0)

        with col2:
            month_names = ["Todos", "Enero","Febrero","Marzo","Abril","Mayo","Junio",
                           "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
            selected_month_idx = st.selectbox("Mes", range(len(month_names)),
                                              format_func=lambda x: month_names[x])

        with col3:
            cat_result = db.table("invoice_categories").select("id, name").execute()
            cat_options = {"Todas": None}
            for c in (cat_result.data or []):
                cat_options[c["name"]] = c["id"]
            selected_cat = st.selectbox("Categoría", list(cat_options.keys()))

        with col4:
            status_options = {"Todos": None, "Pendiente": "PENDIENTE",
                              "Pagada": "PAGADA", "Anulada": "ANULADA"}
            selected_status = st.selectbox("Estado", list(status_options.keys()))

    # ── Query con filtros ────────────────────────────────────────────────────
    query = (
        db.table("invoices")
        .select(
            "id, invoice_number, invoice_date, sale_type, total_amount, currency, "
            "status, needs_review, image_url, "
            "suppliers(name), invoice_categories(name, color_hex)"
        )
        .eq("fiscal_year", selected_year)
        .order("invoice_date", desc=True)
    )

    if selected_month_idx > 0:
        query = query.eq("fiscal_month", selected_month_idx)
    if cat_options[selected_cat]:
        query = query.eq("category_id", cat_options[selected_cat])
    if status_options[selected_status]:
        query = query.eq("status", status_options[selected_status])

    result = query.execute()
    invoices = result.data or []

    # ── Filtro de texto libre ────────────────────────────────────────────────
    if search_text:
        q = search_text.strip().lower()
        invoices = [
            inv for inv in invoices
            if q in (inv.get("invoice_number") or "").lower()
            or q in ((inv.get("suppliers") or {}).get("name") or "").lower()
        ]
        if not invoices:
            st.warning(f"Sin resultados para **\"{search_text}\"**. Prueba con otro término.")
            return

    # ── Métricas de resumen ──────────────────────────────────────────────────
    if invoices:
        total = sum(i.get("total_amount", 0) or 0 for i in invoices)
        cash  = sum(i.get("total_amount", 0) or 0 for i in invoices if i.get("sale_type") == "CONTADO")
        credit = total - cash
        needs_review = sum(1 for i in invoices if i.get("needs_review"))

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total facturas",      len(invoices))
        m2.metric("Monto total",         f"${total:,.2f}")
        m3.metric("Contado / Crédito",   f"${cash:,.2f} / ${credit:,.2f}")
        m4.metric("Requieren revisión",  needs_review,
                  delta=f"{'⚠️ ' if needs_review else '✅'}", delta_color="off")
        st.divider()

    # ── Tabla de facturas ────────────────────────────────────────────────────
    if not invoices:
        st.info("No hay facturas con los filtros seleccionados.")
        return

    for inv in invoices:
        _render_invoice_row(inv)


def _render_invoice_row(inv: dict):
    """Renderiza una fila de factura con acciones."""
    db = get_supabase_client()

    supplier_name  = (inv.get("suppliers") or {}).get("name", "Sin proveedor")
    category_name  = (inv.get("invoice_categories") or {}).get("name", "—")
    status         = inv.get("status", "PENDIENTE")
    sale_type      = inv.get("sale_type", "CONTADO")
    inv_id         = inv["id"]

    status_badges = {
        "PENDIENTE": "🟡 Pendiente",
        "APROBADA":  "🔵 Aprobada",
        "PAGADA":    "🟢 Pagada",
        "ANULADA":   "⛔ Anulada",
    }
    sale_badges = {
        "CONTADO": '<span class="badge-contado">Contado</span>',
        "CREDITO": '<span class="badge-credito">Crédito</span>',
    }

    confirm_key = f"confirm_del_inv_{inv_id}"

    with st.container():
        cols = st.columns([3, 2, 1.5, 1.5, 1.5, 1, 1])

        with cols[0]:
            st.markdown(f"**{supplier_name}**")
            st.caption(f"#{inv.get('invoice_number','—')} · {category_name}")

        with cols[1]:
            st.markdown(f"📅 {inv.get('invoice_date','—')}")
            if inv.get("needs_review"):
                st.caption("⚠️ Requiere revisión")

        with cols[2]:
            st.markdown(sale_badges.get(sale_type, sale_type), unsafe_allow_html=True)

        with cols[3]:
            st.markdown(f"**${inv.get('total_amount', 0):,.2f}** {inv.get('currency','USD')}")

        with cols[4]:
            st.markdown(status_badges.get(status, status))

        with cols[5]:
            if inv.get("image_url"):
                st.link_button("🖼️", inv["image_url"])

        with cols[6]:
            if not st.session_state.get(confirm_key):
                if st.button("🗑️", key=f"del_{inv_id}", help="Eliminar factura"):
                    st.session_state[confirm_key] = True
                    st.rerun()
            else:
                if st.button("⚠️ Confirmar", key=f"confirm_btn_{inv_id}", type="primary",
                             help="Haz clic de nuevo para confirmar el borrado"):
                    # Borrar líneas de detalle primero (integridad referencial)
                    db.table("invoice_items").delete().eq("invoice_id", inv_id).execute()
                    db.table("invoices").delete().eq("id", inv_id).execute()
                    st.session_state.pop(confirm_key, None)
                    st.toast("🗑️ Factura eliminada correctamente.", icon="✅")
                    st.rerun()
                if st.button("✖ Cancelar", key=f"cancel_del_{inv_id}"):
                    st.session_state.pop(confirm_key, None)
                    st.rerun()

        # Acción: marcar como pagada (solo crédito pendiente)
        if sale_type == "CREDITO" and status in ("PENDIENTE", "APROBADA"):
            if st.button(f"✅ Marcar pagada", key=f"pay_{inv_id}"):
                db.table("invoices").update({
                    "status":  "PAGADA",
                    "paid_at": datetime.utcnow().isoformat(),
                }).eq("id", inv_id).execute()
                st.success("Factura marcada como pagada y movida al archivo histórico.")
                st.rerun()

        st.divider()


# ── Página: Cuentas por Pagar ────────────────────────────────────────────────

def render_accounts_payable_page():
    """Vista de facturas de crédito pendientes (cuentas por pagar)."""

    db = get_supabase_client()
    st.title("💳 Cuentas por Pagar")
    st.caption("Facturas de crédito pendientes, ordenadas por urgencia de pago.")

    result = db.table("v_accounts_payable").select("*").execute()
    payables = result.data or []

    if not payables:
        st.success("🎉 No tienes cuentas por pagar pendientes.")
        return

    # Métricas de alerta
    total_debt     = sum(p.get("total_amount", 0) or 0 for p in payables)
    overdue        = [p for p in payables if p.get("payment_urgency") == "VENCIDA"]
    due_soon       = [p for p in payables if p.get("payment_urgency") == "POR_VENCER"]

    m1, m2, m3 = st.columns(3)
    m1.metric("Total pendiente",    f"${total_debt:,.2f}", delta_color="off")
    m2.metric("🔴 Vencidas",        len(overdue),  delta=f"${sum(p['total_amount'] for p in overdue):,.2f}", delta_color="inverse")
    m3.metric("🟡 Vencen en 7 días", len(due_soon), delta=f"${sum(p['total_amount'] for p in due_soon):,.2f}", delta_color="off")

    st.divider()

    # Ordenar: vencidas primero
    urgency_order = {"VENCIDA": 0, "POR_VENCER": 1, "AL_DIA": 2}
    payables.sort(key=lambda x: urgency_order.get(x.get("payment_urgency", "AL_DIA"), 3))

    for p in payables:
        urgency   = p.get("payment_urgency", "AL_DIA")
        overdue_d = p.get("days_overdue") or 0

        urgency_style = {
            "VENCIDA":    ("🔴", "#FEE2E2", f"Vencida hace {overdue_d} días"),
            "POR_VENCER": ("🟡", "#FEF9C3", "Vence en menos de 7 días"),
            "AL_DIA":     ("🟢", "#F9FAFB", "Al día"),
        }.get(urgency, ("⚪", "#F9FAFB", ""))

        icon, bg_color, urgency_label = urgency_style

        with st.container():
            st.markdown(
                f"""<div style="background:{bg_color};padding:0.75rem 1rem;
                    border-radius:10px;margin-bottom:0.5rem;border-left:4px solid
                    {'#EF4444' if urgency=='VENCIDA' else '#F59E0B' if urgency=='POR_VENCER' else '#10B981'}">
                    <strong>{icon} {p.get('supplier_name','—')}</strong>
                    &nbsp;·&nbsp; #{p.get('invoice_number','—')}
                    &nbsp;·&nbsp; {p.get('category_name','—')}
                    <br>
                    <small>Emisión: {p.get('invoice_date','—')}
                    &nbsp;|&nbsp; Vence: <strong>{p.get('due_date','—')}</strong>
                    &nbsp;|&nbsp; {urgency_label}</small>
                    </div>""",
                unsafe_allow_html=True,
            )

            cols = st.columns([2, 1, 1])
            with cols[0]:
                st.markdown(f"### ${p.get('total_amount',0):,.2f} {p.get('currency','USD')}")
            with cols[1]:
                if st.button(f"✅ Pagar", key=f"payable_{p['id']}"):
                    db.table("invoices").update({
                        "status":  "PAGADA",
                        "paid_at": datetime.utcnow().isoformat(),
                    }).eq("id", p["id"]).execute()
                    st.success(f"Factura de {p.get('supplier_name')} marcada como pagada.")
                    st.rerun()
            with cols[2]:
                if p.get("image_url"):
                    st.link_button("🖼️ Ver factura", p["image_url"])

            st.divider()
