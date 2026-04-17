"""
modules/inventory.py — Gestión de inventario (tabla: products)
Usa register_inventory_movement RPC para todos los movimientos de stock.
"""

import streamlit as st
import pandas as pd
from modules.database import get_supabase_client


# Mapa de colores para el semáforo de stock
_STATUS_COLOR = {
    "ROJO":     ("#FEF2F2", "#EF4444", "🔴"),
    "AMARILLO": ("#FFFBEB", "#F59E0B", "🟡"),
    "VERDE":    ("#F0FDF4", "#10B981", "🟢"),
}


def render_inventory_page():
    st.title("📦 Gestión de Inventario")
    supabase = get_supabase_client()

    # ── 1. FORMULARIO DE INGRESO RÁPIDO ──────────────────────────────────────
    with st.expander("➕ Cargar Ingreso de Mercancía", expanded=False):
        with st.form("form_inventario", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                nombre   = st.text_input("Producto / Ingrediente")
                cantidad = st.number_input("Cantidad que entra", min_value=0.0, step=0.1)
            with col2:
                unidad   = st.selectbox("Unidad de medida", ["Gramos", "Mililitros", "Unidades", "Kilos", "Litros"])
                minimo   = st.number_input("Stock mínimo de alerta", min_value=0.0)
                costo    = st.number_input("Costo unitario (opcional)", min_value=0.0, step=0.01)

            btn_stock = st.form_submit_button("Añadir al Stock")

            if btn_stock and nombre:
                try:
                    # Buscar si ya existe en products
                    res = supabase.table("products").select("id, current_stock").ilike("name", nombre.strip()).limit(1).execute()

                    if res.data:
                        product_id = res.data[0]["id"]
                        # Registrar movimiento de ENTRADA
                        supabase.rpc("register_inventory_movement", {
                            "p_product_id":      product_id,
                            "p_movement_type":   "ENTRADA",
                            "p_quantity":        cantidad,
                            "p_unit_cost":       costo if costo > 0 else None,
                            "p_reference_type":  "MANUAL",
                            "p_reference_id":    None,
                            "p_reference_date":  None,
                            "p_notes":           "Ingreso manual desde inventario",
                            "p_created_by":      None,
                        }).execute()
                        st.toast(f"✅ Entrada registrada para {nombre}")
                    else:
                        # Crear producto nuevo
                        new_prod = supabase.table("products").insert({
                            "name":             nombre.strip(),
                            "unit_of_measure":  unidad,
                            "current_stock":    0,
                            "min_stock":        minimo,
                            "reorder_point":    minimo,
                            "unit_cost":        costo if costo > 0 else None,
                            "is_active":        True,
                        }).execute()

                        if new_prod.data and cantidad > 0:
                            product_id = new_prod.data[0]["id"]
                            supabase.rpc("register_inventory_movement", {
                                "p_product_id":      product_id,
                                "p_movement_type":   "ENTRADA",
                                "p_quantity":        cantidad,
                                "p_unit_cost":       costo if costo > 0 else None,
                                "p_reference_type":  "MANUAL",
                                "p_reference_id":    None,
                                "p_reference_date":  None,
                                "p_notes":           "Stock inicial al crear producto",
                                "p_created_by":      None,
                            }).execute()
                        st.toast(f"✨ {nombre} registrado en productos")

                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    # ── 2. AJUSTE MANUAL DE STOCK ─────────────────────────────────────────────
    with st.expander("⚖️ Ajuste Manual de Stock", expanded=False):
        try:
            ajuste_res = (
                supabase.table("products")
                .select("id, name, current_stock, unit_of_measure")
                .eq("is_active", True)
                .order("name")
                .execute()
            )
            productos_ajuste = ajuste_res.data or []
        except Exception as e:
            st.error(f"No se pudo cargar el inventario: {e}")
            productos_ajuste = []

        if not productos_ajuste:
            st.info("No hay productos en el inventario todavía.")
        else:
            nombres_ajuste = [p["name"] for p in productos_ajuste]
            prod_por_nombre = {p["name"]: p for p in productos_ajuste}

            with st.form("form_ajuste_stock", clear_on_submit=True):
                selected = st.selectbox(
                    "Producto",
                    options=nombres_ajuste,
                    help="Elige el producto cuyo stock quieres ajustar.",
                )
                ajuste = st.number_input(
                    "Ajuste de cantidad (positivo = entrada, negativo = salida)",
                    value=0.0,
                    step=0.1,
                    format="%.2f",
                    help="Ej: 5.0 suma 5 al stock; -3.0 resta 3.",
                )
                nota_ajuste = st.text_input("Nota (opcional)", placeholder="Ej: Corrección de conteo físico")
                btn_ajuste = st.form_submit_button("Aplicar ajuste", type="primary")

            if btn_ajuste and ajuste != 0:
                prod_row    = prod_por_nombre.get(selected, {})
                current_qty = float(prod_row.get("current_stock") or 0)
                new_qty     = current_qty + ajuste

                if new_qty < 0:
                    st.warning(
                        f"⚠️ El ajuste dejaría **{selected}** en {new_qty:.2f}, "
                        "lo cual es negativo. Revisa la cantidad."
                    )
                else:
                    tipo_mov = "ENTRADA" if ajuste > 0 else "SALIDA"
                    try:
                        supabase.rpc("register_inventory_movement", {
                            "p_product_id":      prod_row["id"],
                            "p_movement_type":   tipo_mov,
                            "p_quantity":        abs(ajuste),
                            "p_unit_cost":       None,
                            "p_reference_type":  "AJUSTE",
                            "p_reference_id":    None,
                            "p_reference_date":  None,
                            "p_notes":           nota_ajuste or f"Ajuste manual ({tipo_mov})",
                            "p_created_by":      None,
                        }).execute()
                        st.success(f"✅ **{selected}**: {current_qty:.2f} → {new_qty:.2f}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al registrar movimiento: {e}")

    st.divider()

    # ── 3. TABLA DE EXISTENCIAS CON SEMÁFORO (v_stock_status) ────────────────
    st.subheader("📊 Existencias actuales")

    try:
        stock_res = (
            supabase.table("v_stock_status")
            .select("*")
            .order("name")
            .execute()
        )
        stock_data = stock_res.data or []
    except Exception as e:
        st.error(f"No se pudo cargar el inventario: {e}")
        stock_data = []

    if stock_data:
        df = pd.DataFrame(stock_data)

        # Renderizar tabla con semáforo
        st.markdown("""
        <style>
        .inv-badge {
            display:inline-block;
            padding:2px 10px;
            border-radius:20px;
            font-size:0.75rem;
            font-weight:600;
        }
        </style>
        """, unsafe_allow_html=True)

        # Construir HTML de la tabla
        rows_html = ""
        for _, row in df.iterrows():
            status = row.get("stock_status", "VERDE")
            bg, color, icon = _STATUS_COLOR.get(status, ("#F0FDF4", "#10B981", "🟢"))
            label  = row.get("status_label", status)
            name   = row.get("name", "—")
            stock  = float(row.get("current_stock") or 0)
            unit   = row.get("unit_of_measure", "—")
            minimo = float(row.get("min_stock") or 0)

            rows_html += f"""
            <tr>
                <td style="padding:0.55rem 0.8rem;font-weight:500">{name}</td>
                <td style="padding:0.55rem 0.8rem;text-align:right">{stock:.2f}</td>
                <td style="padding:0.55rem 0.8rem">{unit}</td>
                <td style="padding:0.55rem 0.8rem;text-align:right">{minimo:.2f}</td>
                <td style="padding:0.55rem 0.8rem">
                    <span class="inv-badge" style="background:{bg};color:{color}">
                        {icon} {label}
                    </span>
                </td>
            </tr>"""

        st.markdown(f"""
        <table style="width:100%;border-collapse:collapse;font-size:0.9rem">
            <thead>
                <tr style="border-bottom:2px solid #E2E8F0;color:#64748B;font-size:0.75rem;text-transform:uppercase">
                    <th style="padding:0.5rem 0.8rem;text-align:left">Producto</th>
                    <th style="padding:0.5rem 0.8rem;text-align:right">Stock actual</th>
                    <th style="padding:0.5rem 0.8rem;text-align:left">Unidad</th>
                    <th style="padding:0.5rem 0.8rem;text-align:right">Mínimo</th>
                    <th style="padding:0.5rem 0.8rem;text-align:left">Estado</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
        """, unsafe_allow_html=True)

        # ── 4. EDICIÓN INLINE (data_editor sobre products) ────────────────────
        st.divider()
        with st.expander("✏️ Editar datos del producto (nombre, unidad, mínimos)", expanded=False):
            st.info("💡 Haz doble clic en una celda para corregir. Los cambios se guardan automáticamente.")

            prod_res = (
                supabase.table("products")
                .select("id, name, unit_of_measure, min_stock, reorder_point, unit_cost, is_active")
                .eq("is_active", True)
                .order("name")
                .execute()
            )
            prod_df = pd.DataFrame(prod_res.data or [])

            if not prod_df.empty:
                edited_df = st.data_editor(
                    prod_df,
                    column_config={
                        "id":             None,
                        "name":           st.column_config.TextColumn("Producto", width="medium"),
                        "unit_of_measure":st.column_config.TextColumn("Unidad"),
                        "min_stock":      st.column_config.NumberColumn("Stock mínimo", format="%.2f"),
                        "reorder_point":  st.column_config.NumberColumn("Punto de reorden", format="%.2f"),
                        "unit_cost":      st.column_config.NumberColumn("Costo unitario", format="%.4f"),
                        "is_active":      None,
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="products_editor",
                )

                if not edited_df.equals(prod_df):
                    for i, row in edited_df.iterrows():
                        original_row = prod_df.iloc[i]
                        if not row.equals(original_row):
                            supabase.table("products").update({
                                "name":            row["name"],
                                "unit_of_measure": row["unit_of_measure"],
                                "min_stock":       row["min_stock"],
                                "reorder_point":   row["reorder_point"],
                                "unit_cost":       row["unit_cost"],
                            }).eq("id", row["id"]).execute()
                    st.rerun()

        # ── 5. DESACTIVAR PRODUCTO (soft delete) ──────────────────────────────
        st.divider()
        with st.expander("🗑️ Desactivar producto", expanded=False):
            product_names = [row.get("name") for row in stock_data]
            to_delete = st.selectbox(
                "Selecciona el producto a desactivar",
                options=product_names,
                key="delete_product_select",
            )

            confirm_del_key = f"confirm_del_product_{to_delete}"

            if not st.session_state.get(confirm_del_key):
                if st.button("🗑️ Desactivar", key="btn_delete_product", type="secondary"):
                    st.session_state[confirm_del_key] = True
                    st.rerun()
            else:
                st.warning(
                    f"¿Seguro que quieres desactivar **{to_delete}**? "
                    "El producto dejará de aparecer en el inventario activo."
                )
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("⚠️ Sí, desactivar", key="confirm_delete_product", type="primary"):
                        supabase.table("products").update({"is_active": False}).ilike("name", to_delete).execute()
                        st.session_state.pop(confirm_del_key, None)
                        st.toast(f"🗑️ {to_delete} desactivado del inventario.", icon="✅")
                        st.rerun()
                with col_no:
                    if st.button("✖ Cancelar", key="cancel_delete_product"):
                        st.session_state.pop(confirm_del_key, None)
                        st.rerun()
    else:
        st.info("Aún no tienes productos en el inventario.")
