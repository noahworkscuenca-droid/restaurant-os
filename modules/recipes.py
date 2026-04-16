"""
modules/recipes.py — Gestión de recetas (escandallo de platos)
DB columns: dish_name, ingredient, quantity, unit
"""

import streamlit as st
import pandas as pd
from modules.database import get_supabase_client


def render_recipes_page():
    st.markdown(
        '<h3><i class="fas fa-book-open"></i> Recetas (Mapeo de Ingredientes)</h3>',
        unsafe_allow_html=True,
    )
    st.write("Conecta cada plato de Loyverse con los ingredientes que consume del inventario.")

    try:
        supabase = get_supabase_client()
    except Exception as e:
        st.error(f"No se pudo conectar a la base de datos: {e}")
        return

    # ── Cargar ingredientes del inventario ────────────────────────────────────
    try:
        inv_res = (
            supabase.table("inventory")
            .select("ingredient_name, unit")
            .order("ingredient_name")
            .execute()
        )
        inv_items = {
            row["ingredient_name"]: row.get("unit", "")
            for row in (inv_res.data or [])
        }
    except Exception as e:
        st.warning(f"No se pudo cargar el inventario: {e}")
        inv_items = {}

    # ── Formulario ────────────────────────────────────────────────────────────
    st.subheader("Añadir regla de receta")

    with st.form("form_receta", clear_on_submit=True):
        c1, c2, c3 = st.columns([2, 2, 1])
        dish_name  = c1.text_input("Plato (nombre en Loyverse)", placeholder="Ej: Hamburguesa Sencilla")

        if inv_items:
            ingredient = c2.selectbox("Ingrediente a descontar", list(inv_items.keys()))
        else:
            st.info("⚠️ No hay ingredientes en inventario. Agrega en 📦 Inventario primero.")
            ingredient = c2.text_input("Ingrediente (manual)", placeholder="Ej: Tomate")

        quantity = c3.number_input("Cantidad", min_value=0.001, step=0.001, format="%.3f")

        # Unidad automática si el ingrediente ya tiene una en inventario
        unit_default = inv_items.get(ingredient, "g") if inv_items else "g"
        unit = st.selectbox("Unidad", ["g", "kg", "ml", "l", "unidades"],
                            index=["g", "kg", "ml", "l", "unidades"].index(unit_default)
                            if unit_default in ["g", "kg", "ml", "l", "unidades"] else 0)

        submitted = st.form_submit_button("💾 Guardar regla", type="primary")

    if submitted:
        if not dish_name.strip():
            st.warning("Escribe el nombre del plato.")
        elif not ingredient or not str(ingredient).strip():
            st.warning("Selecciona o escribe un ingrediente.")
        elif quantity <= 0:
            st.warning("La cantidad debe ser mayor que 0.")
        else:
            try:
                supabase.table("recipes").insert({
                    "dish_name":  dish_name.strip(),
                    "ingredient": str(ingredient).strip(),
                    "quantity":   quantity,
                    "unit":       unit,
                }).execute()
                st.success(
                    f"✅ Guardado: **{ingredient}** ({quantity} {unit}) → **{dish_name}**"
                )
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

    st.divider()

    # ── Tabla de recetas ──────────────────────────────────────────────────────
    st.subheader("📋 Reglas registradas")

    try:
        recipes_res = (
            supabase.table("recipes")
            .select("*")
            .order("dish_name")
            .execute()
        )
        rows = recipes_res.data or []
    except Exception as e:
        st.error(f"Error al cargar recetas: {e}")
        rows = []

    if not rows:
        st.info("Aún no hay reglas. Usa el formulario de arriba para crear la primera.")
    else:
        df = pd.DataFrame(rows)
        display_cols = [c for c in ["dish_name", "ingredient", "quantity", "unit"] if c in df.columns]
        st.dataframe(
            df[display_cols].rename(columns={
                "dish_name":  "Plato",
                "ingredient": "Ingrediente",
                "quantity":   "Cantidad",
                "unit":       "Unidad",
            }),
            hide_index=True,
            use_container_width=True,
        )

        # ── Eliminar ──────────────────────────────────────────────────────────
        if "id" in df.columns:
            st.divider()
            with st.expander("🗑️ Eliminar regla", expanded=False):
                opciones = {
                    f"{r['dish_name']} — {r['ingredient']} ({r.get('quantity','')} {r.get('unit','')})": r["id"]
                    for r in rows
                }
                selected_label = st.selectbox(
                    "Selecciona la regla a eliminar",
                    options=list(opciones.keys()),
                    key="recipe_delete_select",
                )
                if st.button("🗑️ Eliminar seleccionada", key="btn_delete_recipe"):
                    rid = opciones[selected_label]
                    try:
                        supabase.table("recipes").delete().eq("id", rid).execute()
                        st.toast("Regla eliminada.", icon="✅")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al eliminar: {e}")
