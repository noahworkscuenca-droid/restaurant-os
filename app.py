from dotenv import load_dotenv
load_dotenv()  # Carga SUPABASE_URL, SUPABASE_SERVICE_KEY, GEMINI_API_KEY desde .env

import time
import streamlit as st

# 1. Configuración de pantalla
st.set_page_config(page_title="Divende OS", layout="wide", page_icon="🍽️")

# 2. CSS personalizado + FontAwesome
try:
    with open("style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    pass
st.markdown(
    '<link rel="stylesheet" '
    'href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">',
    unsafe_allow_html=True,
)


# ── Pantalla de Login ────────────────────────────────────────────────────────
def check_password() -> bool:
    """Pantalla de inicio de sesión con usuario y contraseña."""
    if st.session_state.get("logged_in"):
        return True

    # Ocultar sidebar hasta que haya sesión
    st.markdown("""
        <style>
        [data-testid="stSidebar"] { display: none !important; }
        </style>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown("<br><br>", unsafe_allow_html=True)

        st.markdown(
            "<h1 style='text-align:center;font-size:3rem;margin-bottom:0'>🍽️</h1>"
            "<h2 style='text-align:center;margin-top:0.3rem;margin-bottom:0.1rem'>Divende OS</h2>"
            "<p style='text-align:center;color:#94A3B8;margin-top:0;margin-bottom:1.5rem'>"
            "Bienvenido · Inicia sesión para continuar</p>",
            unsafe_allow_html=True,
        )

        with st.form("login_form", border=True):
            usuario  = st.text_input("✉️ Correo electrónico o usuario", placeholder="ejemplo@correo.com")
            password = st.text_input("🔑 Contraseña", type="password", placeholder="••••••••")
            st.markdown("<br>", unsafe_allow_html=True)
            submit = st.form_submit_button(
                "Iniciar sesión →", type="primary", use_container_width=True
            )

            if submit:
                correct = st.secrets.get("APP_PASSWORD", "admin123")
                if usuario == "":
                    st.warning("Por favor, ingresa tu usuario o correo.")
                elif password == correct:
                    st.session_state.logged_in = True
                    st.session_state.usuario_actual = usuario.split("@")[0].capitalize()
                    st.success(f"¡Acceso concedido! Bienvenido, {st.session_state.usuario_actual} 👋")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta. Intenta de nuevo.")

        st.markdown(
            "<p style='text-align:center;font-size:0.78rem;color:#475569;margin-top:1rem'>"
            "Acceso con Google — próximamente</p>",
            unsafe_allow_html=True,
        )

    return False


# ── Guardián: detiene la app si no hay sesión ────────────────────────────────
if not check_password():
    st.stop()

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
    st.markdown(
        '<h2 style="color:white;margin-bottom:0">'
        '<i class="fas fa-utensils"></i> Divende OS</h2>',
        unsafe_allow_html=True,
    )
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
    st.caption("v2.0 · Noah Cuenca")

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
