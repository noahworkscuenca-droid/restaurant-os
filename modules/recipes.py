import streamlit as st
from modules.database import get_supabase_client

def render_recipes_page():
    st.title("🍳 Gestión de Recetas")
    
    # Conexión protegida para evitar pantallas rojas
    try:
        supabase = get_supabase_client()
    except:
        st.error("No se detectan las llaves de Supabase en el archivo .env")
        return

    if 'lista_productos' not in st.session_state:
        st.info("💡 Primero carga tus ventas en la pestaña 'Loyverse POS'.")
        return

    productos = st.session_state['lista_productos']
    producto_sel = st.selectbox("Selecciona un plato para editar:", productos)

    st.divider()

    # --- SECCIÓN PARA AÑADIR ---
    with st.form("form_receta"):
        st.subheader(f"Añadir ingrediente a: {producto_sel}")
        col1, col2 = st.columns(2)
        with col1:
            nombre_ing = st.text_input("Nombre del ingrediente")
        with col2:
            cantidad = st.number_input("Cantidad necesaria", min_value=0.0, step=0.1)
        
        if st.form_submit_button("💾 Guardar Ingrediente"):
            if nombre_ing:
                supabase.table("recipes").insert({
                    "product_name": producto_sel, 
                    "ingredient_name": nombre_ing, 
                    "quantity": cantidad
                }).execute()
                st.success(f"Guardado: {nombre_ing}")
                st.rerun()

    # --- SECCIÓN PARA CORREGIR ERRORES ---
    st.subheader("📋 Ingredientes actuales (Puedes borrar si hay un error)")
    try:
        # Buscamos en la base de datos lo que ya existe para este plato
        res = supabase.table("recipes").select("*").eq("product_name", producto_sel).execute()
        if res.data:
            for item in res.data:
                c_nom, c_can, c_btn = st.columns([3, 1, 1])
                c_nom.write(item['ingredient_name'])
                c_can.write(str(item['quantity']))
                # Botón de borrar con una llave única para cada uno
                if c_btn.button("🗑️ Borrar", key=f"del_{item['id']}"):
                    supabase.table("recipes").delete().eq("id", item['id']).execute()
                    st.warning(f"Eliminado: {item['ingredient_name']}")
                    st.rerun()
        else:
            st.info("Aún no hay ingredientes registrados para este plato.")
    except:
        st.write("Configura tu primera receta para ver la lista aquí.")