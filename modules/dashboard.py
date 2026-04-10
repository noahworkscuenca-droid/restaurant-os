import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from modules.database import get_supabase_client


# ── Helpers ─────────────────────────────────────────────────────────────────
def _kpi_card(label, value, delta=None, delta_color="normal"):
    st.metric(label=label, value=value, delta=delta, delta_color=delta_color)


def render_dashboard():
    st.title("📊 Dashboard Financiero")
    usuario = st.session_state.get("usuario_actual", "")
    if usuario:
        st.caption(f"Bienvenido, {usuario} 👋")

    try:
        supabase = get_supabase_client()
    except Exception:
        st.error("No se puede conectar con Supabase. Verifica tus credenciales.")
        return

    # ── Cargar facturas ──────────────────────────────────────────────────────
    try:
        inv_res = supabase.table("invoices").select(
            "id, supplier, total_amount, payment_type, status, invoice_date, due_date"
        ).execute()
        invoices = inv_res.data or []
    except Exception as e:
        st.error(f"Error al cargar facturas: {e}")
        invoices = []

    df = pd.DataFrame(invoices) if invoices else pd.DataFrame(
        columns=["id", "supplier", "total_amount", "payment_type", "status", "invoice_date", "due_date"]
    )

    if not df.empty:
        df["total_amount"] = pd.to_numeric(df["total_amount"], errors="coerce").fillna(0)
        df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")
        df["due_date"] = pd.to_datetime(df["due_date"], errors="coerce")

    today = datetime.today()
    in_7_days = today + timedelta(days=7)

    # Cálculos
    total_spent   = df["total_amount"].sum() if not df.empty else 0
    cash_spent    = df.loc[df["payment_type"] == "contado", "total_amount"].sum() if not df.empty else 0
    credit_total  = df.loc[df["payment_type"] == "credito", "total_amount"].sum() if not df.empty else 0
    pending_df    = df[(df["status"] == "pendiente") & (df["payment_type"] == "credito")] if not df.empty else pd.DataFrame()
    pending_credit= pending_df["total_amount"].sum()
    overdue_df    = pending_df[pending_df["due_date"] < today] if not pending_df.empty else pd.DataFrame()
    overdue_amt   = overdue_df["total_amount"].sum()
    soon_df       = pending_df[(pending_df["due_date"] >= today) & (pending_df["due_date"] <= in_7_days)] if not pending_df.empty else pd.DataFrame()
    soon_amt      = soon_df["total_amount"].sum()
    num_invoices  = len(df)

    # ── Alerta de vencidos ──────────────────────────────────────────────────
    if overdue_amt > 0:
        st.error(
            f"🚨 **{len(overdue_df)} factura{'s' if len(overdue_df) > 1 else ''} vencida{'s' if len(overdue_df) > 1 else ''}** — "
            f"₡{overdue_amt:,.2f} pendientes de pago"
        )
    elif soon_amt > 0:
        st.warning(f"⚠️ **{len(soon_df)} factura{'s' if len(soon_df) > 1 else ''}** vence en los próximos 7 días — ₡{soon_amt:,.2f}")

    # ── KPIs ────────────────────────────────────────────────────────────────
    st.markdown("### Resumen de compras")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _kpi_card("Total compras", f"₡{total_spent:,.2f}")
    with c2:
        _kpi_card("Pagado (contado)", f"₡{cash_spent:,.2f}")
    with c3:
        _kpi_card("Por pagar (crédito)", f"₡{pending_credit:,.2f}",
                  delta=f"₡{overdue_amt:,.2f} vencidas" if overdue_amt > 0 else None,
                  delta_color="inverse" if overdue_amt > 0 else "normal")
    with c4:
        _kpi_card("Facturas cargadas", str(num_invoices))

    st.divider()

    # ── Ventas Loyverse (placeholder) ───────────────────────────────────────
    st.markdown("### Ventas (Loyverse POS)")
    v1, v2, v3 = st.columns(3)
    v1.metric("Ventas hoy", "₡0.00", delta="Sin datos aún")
    v2.metric("Ventas este mes", "₡0.00")
    v3.metric("Ticket promedio", "₡0.00")
    st.caption("💡 Conecta Loyverse en la pestaña **🔄 Loyverse POS** para ver tus ventas aquí.")

    st.divider()

    # ── Gráfico de gastos por fecha ─────────────────────────────────────────
    if not df.empty and df["invoice_date"].notna().any():
        st.markdown("### 📈 Flujo de compras")
        gastos = (
            df.dropna(subset=["invoice_date"])
            .groupby(df["invoice_date"].dt.date)["total_amount"]
            .sum()
            .reset_index()
        )
        gastos.columns = ["Fecha", "Total (₡)"]
        gastos = gastos.sort_values("Fecha")
        st.line_chart(gastos.set_index("Fecha"))

    # ── Facturas recientes ──────────────────────────────────────────────────
    st.markdown("### 🧾 Facturas recientes")
    if not df.empty:
        recent = df.sort_values("invoice_date", ascending=False).head(8)
        table_data = []
        for _, row in recent.iterrows():
            estado = row.get("status", "")
            badge = "🔴 Vencida" if (estado == "pendiente" and pd.notna(row["due_date"]) and row["due_date"] < today) else                     "🟡 Pendiente" if estado == "pendiente" else "🟢 Pagada"
            table_data.append({
                "Proveedor": row.get("supplier", "—"),
                "Monto": f"₡{row['total_amount']:,.2f}",
                "Tipo": row.get("payment_type", "—").capitalize(),
                "Estado": badge,
                "Fecha": row["invoice_date"].strftime("%d/%m/%Y") if pd.notna(row["invoice_date"]) else "—",
            })
        st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)
    else:
        st.info("Aún no hay facturas. Ve a **📷 Escanear Factura** para comenzar.")
