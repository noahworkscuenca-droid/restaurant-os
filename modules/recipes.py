import streamlit as st
import pandas as pd
from modules.database import get_supabase_client


def render_recipes_page():
    st.title("👨‍🍳 Gestión de Recetas")
    st.info(
        "Define qué ingredientes consume cada plato que vendes. "
        "Estos datos permitirán descontar el inventario automáticamente al registrar ventas."
    )

    # ── Conexión protegida ──────────────────────────────────────────────────
    try:
        supabase = get_supabase_client()
    except Exception:
        st.error("No se detectan las llaves de Supabase en el archivo .env")
        return

    # ── 1. Cargar ingredientes del inventario ───────────────────────────────
    try:
        inv_res = supabase.table("inventory").select("name, unit").order("name").execute()
        ingredientes = {item["name"]: item.get("unit", "") for item in inv_res.data} if inv_res.data else {}
    except Exception:
        ingredientes = {}

    # ── 2. Formulario para añadir ingrediente a receta ──────────────────────
    with st.expander("➕ Añadir ingrediente a una receta", expanded=True):
        with st.form("recipe_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            dish = c1.text_input(
                "Nombre del plato (como aparece en Loyverse)",
                placeholder="Ej: Café Americano",
            )

            if ingredientes:
                ingrediente = c2.selectbox("Ingrediente del inventario", list(ingredientes.keys()))
                unidad_auto = ingredientes.get(ingrediente, "")
            else:
                st.warning("⚠️ No hay ingredientes en el Inventario. Agrega primero tus insumos.")
                ingrediente = c2.text_input("Nombre del ingrediente", placeholder="Ej: Granos de Café")
                unidad_auto = ""

            c3, c4 = st.columns(2)
            cantidad = c3.number_input("Cantidad por porción", min_value=0.001, step=0.001, format="%.3f")
            unidad = c4.text_input("Unidad", value=unidad_auto, disabled=bool(unidad_auto))

            submitted = st.form_submit_button("💾 Guardar ingrediente en receta", type="primary", use_container_width=True)
            if submitted:
                if not dish.strip():
                    st.warning("Por favor escribe el nombre del plato.")
                elif not ingrediente:
                    st.warning("Selecciona un ingrediente.")
                else:
                    try:
                        supabase.table("recipes").insert({
                            "dish_name": dish.strip(),
                            "ingredient_name": ingrediente,
                            "quantity_needed": cantidad,
                            "unit": unidad or unidad_auto,
                        }).execute()
                        st.success(f"✅ Guardado: {cantidad:.3f} {unidad or unidad_auto} de **{ingrediente}** → **{dish}**")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")

    # ── 3. Recetario actual ─────────────────────────────────────────────────
    st.subheader("📋 Recetario actual")
    try:
        res = supabase.table("recipes").select("*").order("dish_name").execute()
        if res.data:
            df = pd.DataFrame(res.data)

            # Agrupar por plato
            platos = df["dish_name"].unique()
            for plato in platos:
                df_plato = df[df["dish_name"] == plato].copy()
                with st.expander(f"🍽️ {plato}  ({len(df_plato)} ingrediente{'s' if len(df_plato) > 1 else ''})"):
                    for _, row in df_plato.iterrows():
                        col_nom, col_can, col_del = st.columns([4, 2, 1])
                        col_nom.write(f"**{row['ingredient_name']}**")
                        col_can.write(f"{row['quantity_needed']:.3f} {row.get('unit', '')}")
                        if col_del.button("🗑️", key=f"del_{row['id']}", help="Borrar este ingrediente"):
                            supabase.table("recipes").delete().eq("id", row["id"]).execute()
                            st.rerun()
        else:
            st.info("Aún no tienes recetas creadas. Usa el formulario de arriba para empezar.")
    except Exception as e:
        st.warning(f"No se pudieron cargar las recetas: {e}")
        st.write("Verifica que la tabla `recipes` existe en Supabase con las columnas: dish_name, ingredient_name, quantity_needed, unit")
