from dotenv import load_dotenv
load_dotenv()

import streamlit as st

st.set_page_config(page_title="RestaurantOS", layout="wide", page_icon="🍽️")


# ── Pantalla de Login ──────────────────────────────────────────────────────
def check_password() -> bool:
    """Devuelve True si el usuario ingresó la contraseña correcta."""
    if st.session_state.get("logged_in"):
        return True

    st.markdown("""
        <style>
        [data-testid="stSidebar"] { display: none !important; }
        </style>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(
            "<h1 style='text-align:center;font-size:2.8rem;margin-bottom:0'>🍽️</h1>"
            "<h2 style='text-align:center;margin-top:0.3rem'>RestaurantOS</h2>"
            "<p style='text-align:center;color:#64748B;margin-top:-0.5rem'>"
            "Acceso restringido · Personal autorizado</p>",
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)

        with st.form("login_form"):
            password = st.text_input("Contraseña", type="password", placeholder="••••••••")
            submit = st.form_submit_button(
                "Entrar →", type="primary", use_container_width=True
            )
            if submit:
                correct = st.secrets.get("APP_PASSWORD", "admin123")
                if password == correct:
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta. Intenta de nuevo.")
    return False


# ── Guardián ───────────────────────────────────────────────────────────────
if not check_password():
    st.stop()


# 2. Estilos globales
st.markdown("""
    <style>
    .stApp { background-color: #F1F5F9; }
    .block-container { padding-top: 2rem !important; }
    [data-testid="stSidebar"] { background-color: #1e293b; }
    [data-testid="stSidebar"] * { color: white !important; }
    div[data-testid="stRadio"] > label { display: none !important; }
    div[data-testid="stRadio"] div[role="radiogroup"] > label > div:first-child,
    div[data-testid="stRadio"] > div > label > div:first-child {
        display: none !important;
    }
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
    .status-badge {
        background-color: #dcfce7; color: #166534;
        padding: 8px; border-radius: 6px;
        font-weight: bold; text-align: center; margin-top: 15px;
    }
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
