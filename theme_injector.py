import streamlit as st
from streamlit_option_menu import option_menu

def apply_modern_theme():
    # 1. Inyección del CSS "Minimalist Dark"
    st.markdown("""
        <style>
        /* Ocultar elementos nativos de Streamlit */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        [data-testid="stHeader"] {
            background: transparent !important;
            border-bottom: none !important;
        }
        section[data-testid="stSidebar"] {
            transform: translateX(0) !important;
            min-width: 220px !important;
            width: 220px !important;
        }
        [data-testid="stSidebarCollapsedControl"] {
            display: none !important;
        }
        /* Fondo general */
        .stApp {
            background-color: #0E1117;
            color: #E6EDF3;
            font-family: 'Inter', -apple-system, sans-serif;
        }

        /* ─── KPI Cards ─────────────────────────────────── */
        .kpi-card {
            background-color: #161B22;
            padding: 20px;
            border-radius: 8px;
            border: 1px solid #30363D;
            text-align: center;
            margin-bottom: 1rem;
        }
        .kpi-valor {
            font-size: 2.2rem;
            font-weight: 700;
            color: #FFFFFF;
        }
        .kpi-etiqueta {
            font-size: 0.9rem;
            color: #8B949E;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        /* ─── Action Cards (IA) ──────────────────────────── */
        .action-card {
            background-color: #161B22;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #58A6FF;
            margin-bottom: 1rem;
        }

        /* ─── Indicadores de estado ──────────────────────── */
        .exito-text {
            color: #238636;
            font-weight: 600;
        }

        /* ─── Métricas nativas de Streamlit ──────────────── */
        [data-testid="stMetric"] {
            background-color: #161B22;
            border: 1px solid #30363D;
            padding: 20px;
            border-radius: 8px;
            transition: transform 0.2s ease, border-color 0.2s ease;
        }
        [data-testid="stMetric"]:hover {
            transform: translateY(-2px);
            border-color: #58A6FF;
        }
        [data-testid="stMetricValue"] {
            font-weight: 800 !important;
            color: #FFFFFF !important;
        }

        /* ─── Botones ────────────────────────────────────── */
        .stButton>button {
            background-color: #161B22;
            color: #E6EDF3;
            border-radius: 8px;
            border: 1px solid #58A6FF;
            font-weight: 600;
            padding: 0.5rem 1rem;
            transition: all 0.3s ease;
        }
        .stButton>button:hover {
            background-color: #58A6FF;
            color: #0E1117;
            box-shadow: 0 0 10px rgba(88, 166, 255, 0.35);
        }

        /* ─── Contenedores generales ─────────────────────── */
        div[data-testid="stVerticalBlock"] > div > div {
            border-radius: 8px;
        }

        /* ─── Mobile responsive ──────────────────────────── */
        @media (max-width: 768px) {
            [data-testid="stDataFrame"] > div {
                overflow-x: auto !important;
            }
            .js-plotly-plot, .plot-container {
                max-width: 100% !important;
            }
            .kpi-valor {
                font-size: 1.5rem !important;
            }
            [data-testid="stSidebarCollapsedControl"] {
                top: 0.5rem !important;
                left: 0.5rem !important;
                z-index: 999 !important;
            }
            .block-container {
                padding-left: 0.75rem !important;
                padding-right: 0.75rem !important;
                padding-top: 1rem !important;
            }
            [data-testid="stMetricValue"] {
                font-size: 1.3rem !important;
            }
        }
        </style>
    """, unsafe_allow_html=True)

    # 2. Menú lateral
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
                "nav-link": {
                    "font-size": "14px",
                    "text-align": "left",
                    "margin": "0px",
                    "--hover-color": "#161B22"
                },
                "nav-link-selected": {"background-color": "#161B22", "border-left": "3px solid #58A6FF"},
                "menu-title": {"color": "#E6EDF3", "font-weight": "bold", "padding-bottom": "1rem"}
            }
        )
        st.divider()
        st.markdown('<div style="background-color: #161B22; color: #238636; padding: 8px; border-radius: 6px; border: 1px solid #30363D; font-weight: bold; text-align: center; margin-top: 15px; font-size: 0.85rem;">🟢 Base de datos OK</div>', unsafe_allow_html=True)
        st.caption("v1.0 · Noah Cuenca")

    return selected
