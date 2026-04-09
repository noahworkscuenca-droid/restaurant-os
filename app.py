from dotenv import load_dotenv
load_dotenv()  # Carga SUPABASE_URL, SUPABASE_SERVICE_KEY, GEMINI_API_KEY desde .env

import streamlit as st

# 1. Configuración de pantalla
st.set_page_config(page_title="RestaurantOS", layout="wide", page_icon="🍽️")

# 2. Estilos globales
st.markdown("""
    <style>

    /* ── Fondo general ─────────────────────────────────────────── */
    .stApp { background-color: #F1F5F9; }
    .block-container { padding-top: 2rem !important; }

    /* ── Sidebar ───────────────────────────────────────────────── */
    [data-testid="stSidebar"] { background-color: #1e293b; }
    [data-testid="stSidebar"] * { color: white !important; }

    /* Ocultar label del grupo de radio */
    div[data-testid="stRadio"] > label { display: none !important; }

    /* Ocultar círculos nativos del radio */
    div[data-testid="stRadio"] div[role="radiogroup"] > label > div:first-child,
    div[data-testid="stRadio"] > div > label > div:first-child {
        display: none !important;
    }

    /* Estilo de ítem de navegación */
    div[data-testid="stRadio"] div[role="radiogroup"] > label,
    div[data-testid="stRadio"] > div > label {
        padding: 0.55rem 0.9rem !important;
        border-radius: 8px !important;
        margin-bottom: 3px !important;
        cursor: pointer;
        transition: background 0.15s ease;
        font-size: 0.93rem !important;
        display: block !important;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] > label:hover,
    div[data-testid="stRadio"] > div > label:hover {
        background: rgba(255,255,255,0.10) !important;
    }

    /* ── Badges de tipo de venta ───────────────────────────────── */
    .badge-contado {
        background-color: #dbeafe; color: #1e40af;
        padding: 2px 8px; border-radius: 12px;
        font-size: 0.8em; font-weight: 600;
    }
    .badge-credito {
        background-color: #fef3c7; color: #92400e;
        padding: 2px 8px; border-radius: 12px;
        font-size: 0.8em; font-weight: 600;
    }

    /* ── Badge de estado sidebar ───────────────────────────────── */
    .status-badge {
        background-color: #dcfce7; color: #166534;
        padding: 8px; border-radius: 6px;
        font-weight: bold; text-align: center; margin-top: 15px;
    }

    /* ── Contenedor de tabla ───────────────────────────────────── */
    .table-wrap {
        background: #fff;
        border-radius: 14px;
        padding: 1.2rem 1.4rem 0.5rem;
        box-shadow: 0 1px 8px rgba(0,0,0,0.07);
        border: 1px solid #E2E8F0;
        margin-top: 0.5rem;
    }

    </style>
    """, unsafe_allow_html=True)

# 3. Importaciones de módulos
from modules.dashboard import render_dashboard
from modules.invoice_ocr import render_invoice_upload_page
from modules.accounting import render_accounting_page, render_accounts_payable_page
from modules.inventory import render_inventory_page
from modules.suppliers import render_suppliers_page
from modules.loyverse_sync import render_sync_page
from modules.recipes import render_recipes_page

# 4. Barra Lateral
with st.sidebar:
    st.title("🍽️ RestaurantOS")
    st.divider()
    menu = st.radio(
        "Navegación",
        [
            "📊 Dashboard",
            "📷 Escanear Factura",
            "🧾 Facturas",
            "💳 Cuentas por Pagar",
            "📦 Inventario",
            "🤝 Proveedores",
            "🔄 Loyverse POS",
            "🍳 Recetas",
        ],
        label_visibility="collapsed",
    )
    st.divider()
    st.markdown('<div class="status-badge">🟢 Base de datos OK</div>', unsafe_allow_html=True)
    st.caption("v1.0 · Noah Cuenca")

# 5. Enrutamiento
if menu == "📊 Dashboard":
    render_dashboard()
elif menu == "📷 Escanear Factura":
    render_invoice_upload_page()
elif menu == "🧾 Facturas":
    render_accounting_page()
elif menu == "💳 Cuentas por Pagar":
    render_accounts_payable_page()
elif menu == "📦 Inventario":
    render_inventory_page()
elif menu == "🤝 Proveedores":
    render_suppliers_page()
elif menu == "🔄 Loyverse POS":
    render_sync_page()
elif menu == "🍳 Recetas":
    render_recipes_page()
