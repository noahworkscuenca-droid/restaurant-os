"""
modules/dashboard.py — Dashboard financiero de RestaurantOS
Columnas reales de Supabase: invoice_date, supplier_id, total_amount, sale_type, status
"""

from datetime import date
import streamlit as st
import pandas as pd
from modules.database import get_supabase_client


# ── Helpers de tarjetas ───────────────────────────────────────────────────────

def _kpi_card(label: str, value: str, sublabel: str = "", accent: str = "#6366F1") -> str:
    return f"""
    <div style="background:#fff;border-radius:14px;padding:1.2rem 1.4rem;
                box-shadow:0 1px 8px rgba(0,0,0,0.07);border-top:4px solid {accent};
                min-height:110px;">
        <p style="margin:0;font-size:0.7rem;font-weight:600;color:#9CA3AF;
                  text-transform:uppercase;letter-spacing:0.07em;">{label}</p>
        <p style="margin:0.3rem 0 0.2rem;font-size:1.85rem;font-weight:800;
                  color:#0F172A;line-height:1.1;">{value}</p>
        <p style="margin:0;font-size:0.78rem;color:#94A3B8;">{sublabel}</p>
    </div>"""


def _alert_card(icon: str, title: str, body: str, accent: str, bg: str) -> str:
    return f"""
    <div style="background:{bg};border-radius:14px;padding:1.1rem 1.3rem;
                box-shadow:0 1px 8px rgba(0,0,0,0.06);border-left:5px solid {accent};
                min-height:95px;">
        <p style="margin:0;font-size:1.6rem;line-height:1;">{icon}</p>
        <p style="margin:0.35rem 0 0.1rem;font-size:0.97rem;font-weight:700;
                  color:#0F172A;">{title}</p>
        <p style="margin:0;font-size:0.8rem;color:#64748B;">{body}</p>
    </div>"""


# ── Render principal ──────────────────────────────────────────────────────────

def render_dashboard():
    db    = get_supabase_client()
    today = date.today()

    st.markdown(
        '<h3><i class="fas fa-chart-line"></i> Dashboard</h3>',
        unsafe_allow_html=True,
    )
    st.caption(f"Resumen al {today.strftime('%d de %B de %Y')}")

    # ── Cargar todas las facturas (sin joins para evitar errores de FK) ───────
    try:
        res = (
            db.table("invoices")
            .select("id, invoice_date, total_amount, sale_type, status, created_at")
            .neq("status", "ANULADA")
            .order("created_at", desc=True)
            .execute()
        )
        all_invoices = res.data or []
    except Exception as e:
        st.error(f"⚠️ Error al cargar facturas: {e}")
        all_invoices = []

    # ── Métricas globales ─────────────────────────────────────────────────────
    if not all_invoices:
        st.info("📭 Aún no hay facturas registradas. ¡Empieza escaneando una!")
    else:
        total_spend    = sum(float(i.get("total_amount") or 0) for i in all_invoices)
        total_invoices = len(all_invoices)
        avg_amount     = total_spend / total_invoices if total_invoices else 0.0

        m1, m2, m3 = st.columns(3)
        m1.metric("💰 Gasto total",          f"₡{total_spend:,.2f}")
        m2.metric("🧾 Facturas registradas", str(total_invoices))
        m3.metric("📊 Promedio por factura", f"₡{avg_amount:,.2f}")

        # Gráfico de gasto acumulado por día
        st.markdown(
            "<p style='margin:1.5rem 0 0.4rem;font-size:0.78rem;font-weight:700;"
            "color:#64748B;text-transform:uppercase;letter-spacing:0.08em;'>"
            "Gasto acumulado por día</p>",
            unsafe_allow_html=True,
        )
        df = pd.DataFrame(all_invoices)
        _date_col = (
            df["invoice_date"].fillna(df["created_at"])
            if "invoice_date" in df.columns and "created_at" in df.columns
            else df.get("invoice_date", df.get("created_at"))
        )
        df["_fecha"]       = pd.to_datetime(_date_col, errors="coerce").dt.date
        df["total_amount"] = pd.to_numeric(df["total_amount"], errors="coerce").fillna(0)

        df_daily = (
            df.dropna(subset=["_fecha"])
            .groupby("_fecha")["total_amount"]
            .sum()
            .reset_index()
            .rename(columns={"_fecha": "Fecha", "total_amount": "Gasto (₡)"})
            .sort_values("Fecha")
        )
        if not df_daily.empty:
            st.line_chart(df_daily.set_index("Fecha")["Gasto (₡)"])

    st.divider()

    # ── KPIs del mes: contado vs crédito ─────────────────────────────────────
    st.markdown(
        "<p style='margin:0 0 0.6rem;font-size:0.78rem;font-weight:700;"
        "color:#64748B;text-transform:uppercase;letter-spacing:0.08em;'>"
        "Resumen general</p>",
        unsafe_allow_html=True,
    )

    total_spent    = sum(float(i.get("total_amount") or 0) for i in all_invoices)
    cash_spent     = sum(
        float(i.get("total_amount") or 0) for i in all_invoices
        if (i.get("sale_type") or "").upper() == "CONTADO"
    )
    pending_credit = sum(
        float(i.get("total_amount") or 0) for i in all_invoices
        if (i.get("sale_type") or "").upper() == "CREDITO"
        and (i.get("status") or "") in ("PENDIENTE", "APROBADA")
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(_kpi_card("Total compras",    f"₡{total_spent:,.2f}",    "Todas las facturas",  "#6366F1"), unsafe_allow_html=True)
    c2.markdown(_kpi_card("Pagado (contado)", f"₡{cash_spent:,.2f}",    "Facturas de contado", "#10B981"), unsafe_allow_html=True)
    c3.markdown(_kpi_card("Por pagar",        f"₡{pending_credit:,.2f}", "Crédito pendiente",
                          "#F59E0B" if pending_credit > 0 else "#10B981"),                                  unsafe_allow_html=True)
    c4.markdown(_kpi_card("Facturas cargadas", str(len(all_invoices)),   "Total registradas",   "#3B82F6"), unsafe_allow_html=True)

    # ── Alertas de inventario y cuentas ──────────────────────────────────────
    st.markdown(
        "<p style='margin:2rem 0 0.6rem;font-size:0.78rem;font-weight:700;"
        "color:#64748B;text-transform:uppercase;letter-spacing:0.08em;'>"
        "Alertas activas</p>",
        unsafe_allow_html=True,
    )

    red_stock = yellow_stock = overdue_count = 0
    overdue_amount = 0.0

    try:
        s = db.table("v_stock_status").select("stock_status").execute()
        stock_data   = s.data or []
        red_stock    = sum(1 for x in stock_data if x.get("stock_status") == "ROJO")
        yellow_stock = sum(1 for x in stock_data if x.get("stock_status") == "AMARILLO")
    except Exception:
        pass

    try:
        p = db.table("v_accounts_payable").select("payment_urgency, total_amount").execute()
        payables     = p.data or []
        overdue_count  = sum(1 for x in payables if x.get("payment_urgency") == "VENCIDA")
        overdue_amount = sum(float(x.get("total_amount") or 0) for x in payables
                             if x.get("payment_urgency") == "VENCIDA")
    except Exception:
        pass

    a1, a2, a3 = st.columns(3)
    a1.markdown(
        _alert_card("🔴", f"{red_stock} producto(s) críticos",  "Stock bajo mínimo",       "#EF4444", "#FEF2F2")
        if red_stock > 0 else
        _alert_card("🟢", "Sin stock crítico",                  "Todos los niveles OK",    "#10B981", "#F0FDF4"),
        unsafe_allow_html=True,
    )
    a2.markdown(
        _alert_card("🟡", f"{yellow_stock} producto(s) bajos", "Reabastecer pronto",      "#F59E0B", "#FFFBEB")
        if yellow_stock > 0 else
        _alert_card("🟢", "Stock saludable",                   "Sin alertas de stock",    "#10B981", "#F0FDF4"),
        unsafe_allow_html=True,
    )
    a3.markdown(
        _alert_card("🔴", f"{overdue_count} factura(s) vencida(s)",
                    f"₡{overdue_amount:,.2f} pendientes",           "#EF4444", "#FEF2F2")
        if overdue_count > 0 else
        _alert_card("🟢", "Sin facturas vencidas",                  "Cuentas al día",      "#10B981", "#F0FDF4"),
        unsafe_allow_html=True,
    )

    # ── Últimas 5 facturas (sin join a suppliers) ─────────────────────────────
    st.markdown(
        "<p style='margin:2rem 0 0.6rem;font-size:0.78rem;font-weight:700;"
        "color:#64748B;text-transform:uppercase;letter-spacing:0.08em;'>"
        "Últimas 5 facturas</p>",
        unsafe_allow_html=True,
    )

    if not all_invoices:
        st.info("Aún no hay facturas. Usa 📷 Escanear Factura para cargar la primera.")
    else:
        recientes = all_invoices[:5]
        rows = [
            {
                "Fecha":   r.get("invoice_date") or r.get("created_at", "—")[:10],
                "Monto":   f"₡{float(r.get('total_amount') or 0):,.2f}",
                "Tipo":    r.get("sale_type", "—"),
                "Estado":  r.get("status", "—"),
            }
            for r in recientes
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
