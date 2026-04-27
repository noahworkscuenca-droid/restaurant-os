from dotenv import load_dotenv
load_dotenv()

import os
import time
import streamlit as st
from supabase import create_client, Client

st.set_page_config(
    page_title="RestaurantOS",
    layout="wide",
    page_icon="🍽️",
    initial_sidebar_state="expanded",
)

# ── Supabase client (anon key — for auth) ──────────────────────────────────────────────
SUPABASE_URL      = os.getenv("SUPABASE_URL")      or st.secrets.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") or st.secrets.get("SUPABASE_ANON_KEY", "")

_supabase: Client = (
    create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    if SUPABASE_URL and SUPABASE_ANON_KEY else None
)

APP_URL     = st.secrets.get("APP_URL", "https://restaurant-o-iyyk7iuzmdrks8pthdwkeq.streamlit.app/")
ADMIN_EMAIL = st.secrets.get("ADMIN_EMAIL", "noahworkscuenca@gmail.com")

# ── Plan hierarchy helper ─────────────────────────────────────────────────────────────────
PLAN_HIERARCHY = ["free", "basico", "profesional", "enterprise"]

def has_plan(min_plan: str) -> bool:
    """True if the logged-in user's plan is >= min_plan."""
    try:
        return (
            PLAN_HIERARCHY.index(st.session_state.get("user_plan", "free"))
            >= PLAN_HIERARCHY.index(min_plan)
        )
    except ValueError:
        return False

# ── Session helpers ───────────────────────────────────────────────────────────────────────────────────
def _set_session(user):
    meta = user.user_metadata or {}
    name = (
        meta.get("full_name")
        or meta.get("name")
        or user.email.split("@")[0]
    )
    st.session_state.logged_in      = True
    st.session_state.user_id        = user.id
    st.session_state.user_email     = user.email
    st.session_state.usuario_actual = name.split()[0].capitalize()
    _load_user_plan(user.id)

def _load_user_plan(user_id: str):
    if not _supabase:
        st.session_state.user_plan = "free"
        st.session_state.is_admin  = False
        return
    try:
        res = (
            _supabase.table("profiles")
            .select("plan, is_admin")
            .eq("id", user_id)
            .single()
            .execute()
        )
        st.session_state.user_plan = res.data.get("plan", "free")
        st.session_state.is_admin  = res.data.get("is_admin", False)
    except Exception:
        st.session_state.user_plan = "free"
        st.session_state.is_admin  = False

# ── Handle Google OAuth callback ────────────────────────────────────────────────────────────────
def _handle_oauth_callback():
    code = st.query_params.get("code")
    if not code or not _supabase:
        return
    try:
        session = _supabase.auth.exchange_code_for_session({"auth_code": code})
        _set_session(session.user)
        st.query_params.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Error al iniciar sesión con Google: {e}")
        st.query_params.clear()

# ── Handle Stripe return ──────────────────────────────────────────────────────────────────────────────────
def _handle_stripe_return():
    if st.query_params.get("payment") == "success":
        st.toast("✅ ¡Pago completado! Tu plan se activará en unos segundos.", icon="✅")
        if st.session_state.get("user_id"):
            _load_user_plan(st.session_state.user_id)
        st.query_params.clear()

_handle_oauth_callback()
_handle_stripe_return()

# ── Login screen ───────────────────────────────────────────────────────────────────────────────────────
LOGIN_CSS = """
<style>
[data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 60%, #0f172a 100%);
    min-height: 100vh;
}
[data-testid="stMain"] { background: transparent !important; }
[data-testid="stHeader"] { background: transparent !important; }
.login-card {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 20px;
    padding: 2.8rem 2.2rem 2.2rem;
    backdrop-filter: blur(16px);
    box-shadow: 0 8px 48px rgba(0,0,0,0.5), 0 1px 0 rgba(255,255,255,0.06) inset;
    margin-top: 0.5rem;
}
.login-logo {
    font-size: 3.8rem;
    text-align: center;
    display: block;
    margin-bottom: 0.4rem;
    filter: drop-shadow(0 0 20px rgba(249,115,22,0.65));
}
.login-title {
    text-align: center;
    font-size: 2rem;
    font-weight: 700;
    color: #f1f5f9;
    margin: 0 0 0.25rem;
    letter-spacing: -0.5px;
}
.login-sub {
    text-align: center;
    color: #64748b;
    font-size: 0.88rem;
    margin: 0 0 1.8rem;
}
[data-testid="stTabs"] [data-baseweb="tab"] { color: #94a3b8 !important; }
[data-testid="stTabs"] [aria-selected="true"] { color: #f97316 !important; }
[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background-color: #f97316 !important; }
</style>
"""

def check_password() -> bool:
    if st.session_state.get("logged_in"):
        return True

    st.markdown(
        "<style>[data-testid='stSidebar']{display:none!important}</style>",
        unsafe_allow_html=True,
    )
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1.25, 1])
    with col:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
            <div class="login-card">
                <span class="login-logo">🍽️</span>
                <h2 class="login-title">RestaurantOS</h2>
                <p class="login-sub">Bienvenido · Inicia sesión para continuar</p>
            </div>
        """, unsafe_allow_html=True)

        tab_google, tab_email = st.tabs(["🔵  Google", "📧  Email"])

        with tab_google:
            st.markdown("<br>", unsafe_allow_html=True)
            if _supabase:
                try:
                    res = _supabase.auth.sign_in_with_oauth({
                        "provider": "google",
                        "options": {"redirect_to": APP_URL, "scopes": "email profile"},
                    })
                    google_url = res.url
                except Exception:
                    google_url = None

                if google_url:
                    st.markdown(
                        f'<a href="{google_url}" target="_self" style="display:flex;align-items:center;justify-content:center;gap:10px;width:100%;padding:0.75rem 1.2rem;background:#fff;color:#1f2937;border-radius:10px;font-size:0.95rem;font-weight:600;text-decoration:none;box-shadow:0 2px 10px rgba(0,0,0,0.3);">'
                        '<img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" width="20"/> Continuar con Google</a>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.info("Google OAuth no configurado. Usa el tab de Email.")
            else:
                st.warning("⚠️ Supabase no configurado.")
            st.markdown("<br>", unsafe_allow_html=True)

        with tab_email:
            st.markdown("<br>", unsafe_allow_html=True)
            mode = st.radio(
                "", ["Iniciar sesión", "Crear cuenta"],
                horizontal=True, label_visibility="collapsed", key="auth_mode",
            )
            with st.form("email_form", border=False):
                email    = st.text_input("✉️  Correo", placeholder="ejemplo@correo.com")
                password = st.text_input("🔑  Contraseña", type="password", placeholder="••••••••")
                if mode == "Crear cuenta":
                    nombre = st.text_input("👤  Nombre completo", placeholder="Tu nombre")
                else:
                    nombre = ""
                st.markdown("<br>", unsafe_allow_html=True)
                submit = st.form_submit_button(
                    "Iniciar sesión →" if mode == "Iniciar sesión" else "Registrarse →",
                    type="primary", use_container_width=True,
                )
                if submit:
                    if not email or not password:
                        st.warning("Por favor completa todos los campos.")
                    elif _supabase:
                        try:
                            if mode == "Iniciar sesión":
                                r = _supabase.auth.sign_in_with_password(
                                    {"email": email, "password": password}
                                )
                                _set_session(r.user)
                                st.rerun()
                            else:
                                opts = {}
                                if nombre:
                                    opts = {"options": {"data": {"full_name": nombre}}}
                                r = _supabase.auth.sign_up(
                                    {"email": email, "password": password, **opts}
                                )
                                if r.user:
                                    st.success(
                                        "✅ Cuenta creada. Revisa tu correo para confirmarla "
                                        "y luego inicia sesión."
                                    )
                        except Exception as e:
                            err = str(e)
                            if "Invalid login" in err or "invalid_credentials" in err:
                                st.error("Correo o contraseña incorrectos.")
                            elif "already registered" in err:
                                st.error("Ya existe una cuenta con ese correo. Inicia sesión.")
                            else:
                                st.error(f"Error: {err}")
    return False


if not check_password():
    st.stop()

# ── Module imports ────────────────────────────────────────────────────────────────────────────────────
from modules.dashboard      import render_dashboard
from modules.invoice_ocr    import render_invoice_upload_page
from modules.accounting     import render_accounting_page, render_accounts_payable_page
from modules.inventory      import render_inventory_page
from modules.suppliers      import render_suppliers_page
from modules.loyverse_sync  import render_sync_page
from modules.recipes        import render_recipes_page
from modules.pricing        import render_pricing_page
from modules.billing        import render_billing_page
from modules.admin          import render_admin_page
from theme_injector         import apply_modern_theme

menu = apply_modern_theme()

# ── Router ─────────────────────────────────────────────────────────────────────────────────────────────
if   menu == "Dashboard":         render_dashboard()
elif menu == "Escanear Factura":  render_invoice_upload_page()
elif menu == "Facturas":          render_accounting_page()
elif menu == "Cuentas por Pagar": render_accounts_payable_page()
elif menu == "Inventario":        render_inventory_page()
elif menu == "Proveedores":       render_suppliers_page()
elif menu == "Loyverse POS":      render_sync_page()
elif menu == "Recetas":           render_recipes_page()
elif menu == "Precios":           render_pricing_page()
elif menu == "Mi Plan":           render_billing_page()
elif menu == "Admin":
    if (st.session_state.get("is_admin")
            or st.session_state.get("user_email") == ADMIN_EMAIL):
        render_admin_page()
    else:
        st.error("⛔ Acceso denegado.")
