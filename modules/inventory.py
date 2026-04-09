import streamlit as st
import pandas as pd
from modules.database import get_supabase_client

def render_inventory_page():
    st.title("📦 Gestión de Inventario")
    supabase = get_supabase_client()

    # --- 1. FORMULARIO DE INGRESO RÁPIDO ---
    with st.expander("➕ Cargar Ingreso de Mercancía", expanded=False):
        with st.form("form_inventario", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                nombre = st.text_input("Ingrediente")
                cantidad = st.number_input("Cantidad que entra", min_value=0.0, step=0.1)
            with col2:
                unidad = st.selectbox("Unidad", ["Gramos", "Mililitros", "Unidades", "Kilos"])
                minimo = st.number_input("Alerta de stock mínimo", min_value=0.0)
            
            btn_stock = st.form_submit_button("Añadir al Stock")
            
            if btn_stock and nombre:
                # Lógica de Upsert (Actualizar si existe, insertar si no)
                res = supabase.table("inventory").select("*").eq("ingredient_name", nombre).execute()
                
                try:
                    if res.data:
                        nueva_cant = res.data[0]['current_quantity'] + cantidad
                        supabase.table("inventory").update({
                            "current_quantity": nueva_cant,
                            "updated_at": "now()"
                        }).eq("ingredient_name", nombre).execute()
                        st.toast(f"✅ Stock de {nombre} actualizado")
                    else:
                        supabase.table("inventory").insert({
                            "ingredient_name": nombre, 
                            "current_quantity": cantidad, 
                            "unit": unidad,
                            "min_quantity": minimo
                        }).execute()
                        st.toast(f"✨ {nombre} registrado")
                    
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    st.divider()

    # --- 2. TABLA EDITABLE (CONTROL TOTAL) ---
    st.subheader("📊 Existencias actuales")
    st.info("💡 Haz doble clic en una celda para corregir un error. Se guarda automáticamente.")
    
    # Traemos los datos de Supabase
    stock_res = supabase.table("inventory").select("*").order("ingredient_name").execute()
    
    if stock_res.data:
        # Convertimos a DataFrame
        df = pd.DataFrame(stock_res.data)
        
        # AJUSTE DE HORA: Convertimos UTC a la hora de Costa Rica (CST)
        df['updated_at'] = pd.to_datetime(df['updated_at']).dt.tz_convert('America/Costa_Rica')

        # El Editor de Datos Pro
        edited_df = st.data_editor(
            df,
            column_config={
                "id": None, # Oculto para el usuario
                "ingredient_name": st.column_config.TextColumn("Ingrediente", width="medium"),
                "current_quantity": st.column_config.NumberColumn("Cantidad Actual", format="%.2f"),
                "min_quantity": st.column_config.NumberColumn("Mínimo", format="%.2f"),
                "unit": "Unidad",
                "updated_at": st.column_config.DatetimeColumn(
                    "Último Cambio",
                    format="D MMM, h:mm A", # Formato: 3 Abr, 6:27 PM
                    disabled=True
                )
            },
            hide_index=True,
            width="stretch",
            key="inventory_editor"
        )

        # Lógica para detectar cambios manuales en la tabla
        if not edited_df.equals(df):
            for i, row in edited_df.iterrows():
                original_row = df.iloc[i]
                if not row.equals(original_row):
                    supabase.table("inventory").update({
                        "ingredient_name": row["ingredient_name"],
                        "current_quantity": row["current_quantity"],
                        "unit": row["unit"],
                        "min_quantity": row["min_quantity"],
                        "updated_at": "now()" # Actualiza la hora al editar manualmente
                    }).eq("id", row["id"]).execute()
            st.rerun()
        # --- 3. BORRAR INGREDIENTE ---
        st.divider()
        with st.expander("🗑️ Eliminar ingrediente", expanded=False):
            ingredient_names = df["ingredient_name"].tolist()
            to_delete = st.selectbox(
                "Selecciona el ingrediente a eliminar",
                options=ingredient_names,
                key="delete_ingredient_select",
            )

            confirm_del_key = f"confirm_del_ingredient_{to_delete}"

            if not st.session_state.get(confirm_del_key):
                if st.button("🗑️ Eliminar", key="btn_delete_ingredient", type="secondary"):
                    st.session_state[confirm_del_key] = True
                    st.rerun()
            else:
                st.warning(f"¿Seguro que quieres eliminar **{to_delete}**? Esta acción no se puede deshacer.")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("⚠️ Sí, eliminar", key="confirm_delete_ingredient", type="primary"):
                        supabase.table("inventory").delete().eq("ingredient_name", to_delete).execute()
                        st.session_state.pop(confirm_del_key, None)
                        st.toast(f"🗑️ {to_delete} eliminado del inventario.", icon="✅")
                        st.rerun()
                with col_no:
                    if st.button("✖ Cancelar", key="cancel_delete_ingredient"):
                        st.session_state.pop(confirm_del_key, None)
                        st.rerun()

    else:
        st.info("Aún no tienes ingredientes en el inventario.")