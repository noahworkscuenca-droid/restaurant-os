import streamlit as st


def apply_modern_theme():
    st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stApp {
        background-color: #0E1117;
        color: #FAFAFA;
        font-family: 'Inter', -apple-system, sans-serif;
    }
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
    [data-testid="stMetricValue"] {
        font-weight: 800 !important;
        color: #FFFFFF !important;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
    }
    div[data-testid="stSelectbox"] label {
        font-size: 0.75rem !important;
        font-weight: 700 !important;
        color: #9CA3AF !important;
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(
        "<h2 style='margin:0.5rem 0 0.2rem;color:#FAFAFA;'>🍽️ Divende OS</h2>"
        "<p style='margin:0 0 0.8rem;font-size:0.78rem;color:#64748B;'>v1.0 · Noah Cuenca</p>",
        unsafe_allow_html=True,
    )

    # User badge
    plan   = st.session_state.get("user_plan", "free")
    nombre = st.session_state.get("usuario_actual", "")
    email  = st.session_state.get("user_email", "")

    plan_meta = {
        "free":        ("🆓 Gratuito",    "#64748B"),
        "basico":      ("⭐ Básico",       "#3B82F6"),
        "profesional": ("💎 Profesional",  "#8B5CF6"),
        "enterprise":  ("🏆 Enterprise",   "#F59E0B"),
    }.get(plan, ("🆓 Gratuito", "#64748B"))

    st.markdown(
        f"<div style='background:#1A1C23;border:1px solid #2D303E;border-radius:8px;"
        f"padding:10px 12px;margin-bottom:0.8rem'>"
        f"<div style='font-weight:600;color:#FAFAFA;font-size:0.9rem'>{nombre}</div>"
        f"<div style='font-size:0.7rem;color:#64748B;margin-bottom:5px'>{email}</div>"
        f"<span style='background:{plan_meta[1]}22;color:{plan_meta[1]};"
        f"border:1px solid {plan_meta[1]}44;border-radius:4px;"
        f"padding:2px 8px;font-size:0.68rem;font-weight:700'>{plan_meta[0]}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Navigation menu
    menu_options = [
        "📊 Dashboard",
        "📷 Escanear Factura",
        "🧾 Facturas",
        "💳 Cuentas por Pagar",
        "📦 Inventario",
        "🤝 Proveedores",
        "🔄 Loyverse POS",
        "🍳 Recetas",
        "⭐ Precios",
        "💸 Mi Plan",
    ]

    admin_email = st.secrets.get("ADMIN_EMAIL", "noahworkscuenca@gmail.com")
    if (st.session_state.get("is_admin")
            or st.session_state.get("user_email") == admin_email):
        menu_options.append("🔧 Admin")

    selected_label = st.selectbox(
        "Navegar a", menu_options, label_visibility="collapsed"
    )

    route_map = {
        "📊 Dashboard":         "Dashboard",
        "📷 Escanear Factura":   "Escanear Factura",
        "🧾 Facturas":       "Facturas",
        "💳 Cuentas por Pagar": "Cuentas por Pagar",
        "📦 Inventario":         "Inventario",
        "🤝 Proveedores":      "Proveedores",
        "🔄 Loyverse POS":      "Loyverse POS",
        "🍳 Recetas":           "Recetas",
        "⭐ Precios":           "Precios",
        "💸 Mi Plan":          "Mi Plan",
        "🔧 Admin":           "Admin",
    }

    st.divider()

    if st.button("🚪 Cerrar sesión", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

    return route_map[selected_label]
