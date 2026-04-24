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
    render_pricing_page()
