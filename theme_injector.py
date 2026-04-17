import streamlit as st
from streamlit_option_menu import option_menu

def apply_modern_theme():
    # 1. Inyección del CSS "Dark Tech"
    st.markdown("""
        <style>
        /* Ocultar elementos nativos de Streamlit */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}

        /* Fondo general oscuro y moderno */
        .stApp {
            background-color: #0E1117;
            color: #FAFAFA;
            font-family: 'Inter', -apple-system, sans-serif;
        }

        /* Estilo de Tarjetas para Métricas (Dashboard) */
        [data-testid="stMetric"] {
            background-color: #1A1C23;
            border: 1px solid #2D303E;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
            transition: transform 0.2s ease, border-color 0.2s ease;
        }
        [data-testid="stMetric"]:hover {
            transform: translateY(-2px);
            border-color: #4CAF50;
        }

        /* Botones estilo neón/profesional */
        .stButton>button {
            background-color: #2D303E;
            color: white;
            border-radius: 8px;
            border: 1px solid #4CAF50;
            font-weight: 600;
            padding: 0.5rem 1rem;
            transition: all 0.3s ease;
        }
        .stButton>button:hover {
            background-color: #4CAF50;
            color: #0E1117;
            box-shadow: 0 0 10px rgba(76, 175, 80, 0.4);
            border-color: #4CAF50;
        }

        /* Contenedores generales */
        div[data-testid="stVerticalBlock"] > div > div {
            border-radius: 12px;
        }
        </style>
    """, unsafe_allow_html=True)

    # 2. Creación del menú lateral interactivo
    with st.sidebar:
        st.markdown("<br>", unsafe_allow_html=True)
        selected = option_menu(
            menu_title="Divende OS",
            options=["Dashboard", "Escanear Factura", "Facturas", "Cuentas por Pagar", "Inventario", "Proveedores", "Loyverse POS", "Recetas", "Precios"],
            icons=["bar-chart-line-fill", "camera-fill", "receipt", "credit-card-fill", "box-seam-fill", "people-fill", "arrow-repeat", "journal-richtext", "stars"],
            menu_icon="shop",
            default_index=0,
            styles={
                "container": {"padding": "0!important", "background-color": "transparent"},
                "icon": {"color": "#4CAF50", "font-size": "16px"},
                "nav-link": {
                    "font-size": "14px",
                    "text-align": "left",
                    "margin": "0px",
                    "--hover-color": "#1A1C23"
                },
                "nav-link-selected": {"background-color": "#1E222D"},
                "menu-title": {"color": "#FAFAFA", "font-weight": "bold", "padding-bottom": "1rem"}
            }
        )
        st.divider()
        st.markdown('<div style="background-color: #1A1C23; color: #4CAF50; padding: 8px; border-radius: 6px; border: 1px solid #2D303E; font-weight: bold; text-align: center; margin-top: 15px; font-size: 0.85rem;">🟢 Base de datos OK</div>', unsafe_allow_html=True)
        st.caption("v1.0 · Noah Cuenca")

    return selected
