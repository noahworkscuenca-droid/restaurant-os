from dotenv import load_dotenv
load_dotenv()

import time
import streamlit as st

st.set_page_config(page_title="RestaurantOS", layout="wide", page_icon="🍽️", initial_sidebar_state="expanded")


def check_password() -> bool:
    if st.session_state.get("logged_in"):
        return True

    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(
            "<h1 style='text-align:center;font-size:3rem;margin-bottom:0'>🍽️</h1>"
            "<h2 style='text-align:center;margin-top:0.3rem;margin-bottom:0.1rem'>RestaurantOS</h2>"
            "<p style='text-align:center;color:#64748B;margin-top:0;margin-bottom:1.5rem'>"
            "Bienvenido · Inicia sesión para continuar</p>",
            unsafe_allow_html=True,
        )

        with st.form("login_form", border=True):
            usuario  = st.text_input("✉️ Correo electrónico o usuario", placeholder="ejemplo@correo.com")
            password = st.text_input("🔑 Contraseña", type="password", placeholder="••••••••")
            st.markdown("<br>", unsafe_allow_html=True)
            submit = st.form_submit_button("Iniciar sesión →", type="primary", use_container_width=True)

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

    return False


if not check_password():
    st.stop()

from modules.dashboard import render_dashboard
from modules.invoice_ocr import render_invoice_upload_page
from modules.accounting import render_accounting_page, render_accounts_payable_page
from modules.inventory import render_inventory_page
from modules.suppliers import render_suppliers_page
from modules.loyverse_sync import render_sync_page
from modules.recipes import render_recipes_page
from modules.pricing import render_pricing_page

from theme_injector import apply_modern_theme
menu = apply_modern_theme()

if menu == "Dashboard":
    render_dashboard()
elif menu == "Escanear Factura":
    render_invoice_upload_page()
elif menu == "Facturas":
    render_accounting_page()
elif menu == "Cuentas por Pagar":
    render_accounts_payable_page()
elif menu == "Inventario":
    render_inventory_page()
elif menu == "Proveedores":
    render_suppliers_page()
elif menu == "Loyverse POS":
    render_sync_page()
elif menu == "Recetas":
    render_recipes_page()
elif menu == "Precios":
    render_pricing_page()from dotenv import load_dotenv
load_dotenv()  # Carga SUPABASE_URL, SUPABASE_SERVICE_KEY, GEMINI_API_KEY desde .env

import os
import time
import streamlit as st
from supabase import create_client

# 1. Configuración de pantalla
st.set_page_config(
    page_title="Divende",
    layout="wide",
    page_icon="🍽️",
    initial_sidebar_state="auto",         # desktop: abierto; móvil: cerrado
)

# ── Cliente Supabase (anon key para auth) ────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") or st.secrets.get("SUPABASE_ANON_KEY", "")
_supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY) if SUPABASE_URL and SUPABASE_ANON_KEY else None

APP_URL = "https://restaurant-o-iyyk7iuzmdrks8pthdwkeq.streamlit.app/"


# ── Manejo del callback OAuth (código en query params) ───────────────────────
def _handle_oauth_callback():
    """Si Supabase redirige con ?code=..., intercambia el código por sesión."""
    params = st.query_params
    code = params.get("code")
    if not code or not _supabase:
        return
    try:
        session = _supabase.auth.exchange_code_for_session({"auth_code": code})
        user = session.user
        st.session_state.logged_in = True
        st.session_state.usuario_actual = (user.user_metadata.get("full_name") or
                                           user.email.split("@")[0]).capitalize()
        st.session_state.usuario_email = user.email
        st.query_params.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Error al completar el inicio de sesión con Google: {e}")
        st.query_params.clear()

_handle_oauth_callback()


# ── Pantalla de Login ────────────────────────────────────────────────────────
def check_password() -> bool:
    """Pantalla de inicio de sesión con usuario/contraseña y botón de Google."""
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

        # Encabezado
        st.markdown(
            "<h1 style='text-align:center;font-size:3rem;margin-bottom:0'>🍽️</h1>"
            "<h2 style='text-align:center;margin-top:0.3rem;margin-bottom:0.1rem'>Divende</h2>"
            "<p style='text-align:center;color:#8B949E;margin-top:0;margin-bottom:1.5rem'>"
            "Bienvenido · Inicia sesión para continuar</p>",
            unsafe_allow_html=True,
        )

        # ── Botón de Google ──────────────────────────────────────────────────
        if _supabase:
            try:
                res = _supabase.auth.sign_in_with_oauth({
                    "provider": "google",
                    "options": {
                        "redirect_to": APP_URL,
                        "scopes": "email profile",
                    }
                })
                google_url = res.url
            except Exception:
                google_url = None

            if google_url:
                st.markdown(
                    f"""
                    <a href="{google_url}" target="_self" style="
                        display:flex; align-items:center; justify-content:center; gap:10px;
                        width:100%; padding:0.6rem 1rem;
                        background:#fff; color:#3c4043;
                        border:1px solid #dadce0; border-radius:8px;
                        font-size:0.95rem; font-weight:500;
                        text-decoration:none; margin-bottom:1rem;
                        box-shadow:0 1px 3px rgba(0,0,0,0.12);
                    ">
                        <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" width="20"/>
                        Continuar con Google
                    </a>
                    """,
                    unsafe_allow_html=True,
                )

        # ── Separador ────────────────────────────────────────────────────────
        st.markdown(
            "<div style='display:flex;align-items:center;gap:8px;margin-bottom:1rem'>"
            "<hr style='flex:1;border-color:#30363D'>"
            "<span style='color:#8B949E;font-size:0.8rem'>o</span>"
            "<hr style='flex:1;border-color:#30363D'>"
            "</div>",
            unsafe_allow_html=True,
        )

        # ── Formulario usuario/contraseña ────────────────────────────────────
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
from modules.pricing import render_pricing_page

# ── Sidebar / Navegación ────────────────────────────────────
from theme_injector import apply_modern_theme
menu = apply_modern_theme()

# 5. Enrutamiento
if menu == "Dashboard":
    render_dashboard()
elif menu == "Escanear Factura":
    render_invoice_upload_page()
elif menu == "Facturas":
    render_accounting_page()
elif menu == "Cuentas por Pagar":
    render_accounts_payable_page()
elif menu == "Inventario":
    render_inventory_page()
elif menu == "Proveedores":
    render_suppliers_page()
elif menu == "Loyverse POS":
    render_sync_page()
elif menu == "Recetas":
    render_recipes_page()
elif menu == "Precios":
    render_pricing_page()
