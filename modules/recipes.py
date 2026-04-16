"""
modules/recipes.py — Gestión de recetas (escandallo de platos)
"""

import streamlit as st
import pandas as pd
from modules.database import get_supabase_client


def render_recipes_page():
    st.title("🍳 Recetas")
    st.caption("Define qué ingredientes y cantidades lleva cada plato del menú.")

    try:
        supabase = get_supabase_client()
    except Exception as e:
        st.error(f"No se pudo conectar a la base de datos: {e}")
        return

    # ── Cargar ingredientes disponibles desde inventario ─────────────────────
    try:
        inv_res = (
            supabase.table("inventory")
            .select("ingredient_name")
            .order("ingredient_name")
            .execute()
        )
        ingredientes = [row["ingredient_name"] for row in (inv_res.data or [])]
    except Exception as e:
        st.warning(f"No se pudo cargar el inventario: {e}")
        ingredientes = []

    # ── Formulario: añadir ingrediente a una receta ───────────────────────────
    st.subheader("Añadir ingrediente a una receta")

    with st.form("form_receta", clear_on_submit=True):
        dish_name = st.text_input(
            "Nombre del plato",
            placeholder="Ej: Pollo al grill, Ensalada César…",
        )

        if ingredientes:
            ingredient = st.selectbox(
                "Ingrediente",
                options=ingredientes,
                help="Los ingredientes se toman del módulo de Inventario.",
            )
        else:
            st.info(
                "⚠️ No hay ingredientes en el inventario. "
                "Agrega ingredientes en el módulo 📦 Inventario primero."
            )
            ingredient = st.text_input(
                "Ingrediente (escribe manualmente)",
                placeholder="Ej: Tomate",
            )

        col1, col2 = st.columns(2)
        with col1:
            quantity = st.number_input(
                "Cantidad",
                min_value=0.0,
                step=0.1,
                format="%.3f",
                help="Cantidad de este ingrediente necesaria para una porción.",
            )
        with col2:
            unit = st.selectbox(
                "Unidad",
                options=["g", "kg", "ml", "l", "unidades"],
            )

        submitted = st.form_submit_button("💾 Guardar ingrediente", type="primary")

    if submitted:
        if not dish_name.strip():
            st.warning("Por favor escribe el nombre del plato.")
        elif not ingredient or not str(ingredient).strip():
            st.warning("Por favor selecciona o escribe un ingrediente.")
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
                    f"✅ Guardado: **{ingredient}** ({quantity} {unit}) "
                    f"para **{dish_name}**"
                )
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar en la base de datos: {e}")

    st.divider()

    # ── Tabla de recetas existentes ───────────────────────────────────────────
    st.subheader("📋 Recetas registradas")

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
        st.info("Aún no hay recetas registradas. Usa el formulario de arriba para añadir la primera.")
    else:
        df = pd.DataFrame(rows)

        # Columnas a mostrar (excluir id si existe)
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

        # ── Eliminar una línea de receta ──────────────────────────────────────
        if "id" in df.columns:
            st.divider()
            with st.expander("🗑️ Eliminar línea de receta", expanded=False):
                # Construir etiquetas legibles para el selectbox
                opciones = {
                    f"{r['dish_name']} — {r['ingredient']} ({r.get('quantity','')} {r.get('unit','')})": r["id"]
                    for r in rows
                }
                selected_label = st.selectbox(
                    "Selecciona la línea a eliminar",
                    options=list(opciones.keys()),
                    key="recipe_delete_select",
                )
                if st.button("🗑️ Eliminar línea seleccionada", key="btn_delete_recipe"):
                    rid = opciones[selected_label]
                    try:
                        supabase.table("recipes").delete().eq("id", rid).execute()
                        st.toast("Línea eliminada.", icon="✅")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al eliminar: {e}")
