import pandas as pd
import streamlit as st

def render_sync_page():
    st.title("🔄 Sincronizar Ventas (Loyverse)")
    archivo = st.file_uploader("Sube tu reporte de ventas aquí", type=["csv"])

    if archivo is not None:
        try:
            df = pd.read_csv(archivo)
            st.write(f"### Se detectaron {len(df)} productos")
            st.dataframe(df, width="stretch")
            
            if st.button("🚀 Procesar Ventas", type="primary"):
                # Esto es vital para que la pestaña de Recetas sepa qué platos existen
                st.session_state['lista_productos'] = df['Item name'].unique().tolist()
                st.success("¡Ventas procesadas con éxito!")
                st.balloons()
        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")