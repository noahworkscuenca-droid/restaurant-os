import streamlit as st
from streamlit_option_menu import option_menu

def apply_modern_theme():
    st.markdown("""
        <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        header [data-testid="stSidebarCollapsedControl"],
        [data-testid="stSidebarCollapsedControl"] {
            visibility: visible !important;
            display: flex !important;
        }
        .stApp {
            background-color: #0E1117;
            color: #E6EDF3;
            font-family: 'Inter', -apple-system, sans-serif;
        }
        .kpi-card {
            background-color: #161B22;
            padding: 20px;
            border-radius: 8px;
            border: 1px solid #30363D;
            text-align: center;
            margin-bottom: 1rem;
        }
        .kpi-valor { font-size: 2.2rem; font-weight: 700; color: #FFFFFF; }
        .kpi-etiqueta { font-size: 0.9rem; color: #8B949E; text-transform: uppercase; letter-spacing: 1px; }
        .action-card {
            background-color: #161B22;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #58A6FF;
            margin-bottom: 1rem;
        }
        .exito-text { color: #238636; font-weight: 600; }
        [data-testid="stMetric"] {
            background-color: #161B22;
            border: 1px solid #30363D;
            padding: 20px;
            border-radius: 8px;
        }
        [data-testid="stMetric"]:hover { transform: translateY(-2px); border-color: #58A6FF; }
        [data-testid="stMetricValue"] { font-weight: 800 !important; color: #FFFFFF !important; }
        .stButton>button {
            background-color: #161B22;
            color: #E6EDF3;
            border-radius: 8px;
            border: 1px solid #58A6FF;
            font-weight: 600;
            padding: 0.5rem 1rem;
        }
        .stButton>button:hover { background-color: #58A6FF; color: #0E1117; }
        </style>
    """, unsafe_allow_html=True)

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
                "icon": {"color": "#58A6FF", "font-size": "16px"},
                "nav-link": {"font-size": "14px", "text-align": "left", "margin": "0px", "--hover-color": "#161B22"},
                "nav-link-selected": {"background-color": "#161B22", "border-left": "3px solid #58A6FF"},
                "menu-title": {"color": "#E6EDF3", "font-weight": "bold", "padding-bottom": "1rem"}
            }
        )
        st.divider()
        st.markdown('<div style="background-color:#161B22;color:#238636;padding:8px;border-radius:6px;border:1px solid #30363D;font-weight:bold;text-align:center;font-size:0.85rem;">🟢 Base de datos OK</div>', unsafe_allow_html=True)
        st.caption("v1.0 · Noah Cuenca")

    return selected
