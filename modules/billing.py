import os
import streamlit as st

try:
    import stripe as _stripe_lib
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False

PLAN_ORDER = ["free", "basico", "profesional", "enterprise"]

PLAN_CONFIG = {
    "free": {
        "label":    "Gratuito",
        "price":    "0",
        "emoji":    "U0001F193",
        "color":    "#64748B",
        "features": ["Dashboard básico", "Hasta 10 facturas/mes", "1 usuario"],
        "price_id": None,
    },
    "basico": {
        "label":    "Básico",
        "price":    "29",
        "emoji":    "⭐",
        "color":    "#3B82F6",
        "features": ["Todo lo de Gratuito", "Facturas ilimitadas", "OCR de facturas", "Inventario y proveedores", "Cuentas por pagar"],
        "price_id": "STRIPE_PRICE_BASICO",
    },
    "profesional": {
        "label":    "Profesional",
        "price":    "79",
        "emoji":    "U0001F48E",
        "color":    "#8B5CF6",
        "features": ["Todo lo de Básico", "Sincronización Loyverse POS", "Recetas y costeo", "Precios y márgenes", "Soporte prioritario"],
        "price_id": "STRIPE_PRICE_PROFESIONAL",
    },
    "enterprise": {
        "label":    "Enterprise",
        "price":    "Consultar",
        "emoji":    "U0001F3C6",
        "color":    "#F59E0B",
        "features": ["Todo lo de Profesional", "Múltiples sucursales", "API access", "Manager dedicado", "SLA garantizado"],
        "price_id": "STRIPE_PRICE_ENTERPRISE",
    },
}


def _stripe():
    if not STRIPE_AVAILABLE:
        return None
    key = os.getenv("STRIPE_SECRET_KEY") or st.secrets.get("STRIPE_SECRET_KEY", "")
    if not key:
        return None
    _stripe_lib.api_key = key
    return _stripe_lib


def _create_checkout_url(plan_key, user_email, user_id):
    s = _stripe()
    if not s:
        return None
    secret_key = PLAN_CONFIG[plan_key]["price_id"]
    if not secret_key:
        return None
    price_id = st.secrets.get(secret_key, "")
    if not price_id:
        return None
    app_url = st.secrets.get("APP_URL", "")
    try:
        session = s.checkout.Session.create(
            customer_email=user_email,
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=f"{app_url}?payment=success",
            cancel_url=f"{app_url}?payment=cancelled",
            metadata={"supabase_user_id": user_id, "plan": plan_key},
            allow_promotion_codes=True,
        )
        return session.url
    except Exception as e:
        st.error(f"Error al crear sesión de pago: {e}")
        return None


def _create_portal_url(customer_id):
    s = _stripe()
    if not s or not customer_id:
        return None
    app_url = st.secrets.get("APP_URL", "")
    try:
        session = s.billing_portal.Session.create(customer=customer_id, return_url=app_url)
        return session.url
    except Exception as e:
        st.error(f"Error al abrir portal: {e}")
        return None


def render_billing_page():
    current_plan = st.session_state.get("user_plan", "free")
    user_email   = st.session_state.get("user_email", "")
    user_id      = st.session_state.get("user_id", "")
    current_idx  = PLAN_ORDER.index(current_plan)

    st.title("U0001F4B8 Mi Plan")
    st.markdown("Elige el plan que mejor se adapta a tu restaurante.")
    st.divider()

    cols = st.columns(4)
    for i, (plan_key, cfg) in enumerate(PLAN_CONFIG.items()):
        is_current   = plan_key == current_plan
        border_color = cfg["color"] if is_current else "#2D303E"
        price_str    = f"${cfg['price']}/mes" if cfg["price"].isdigit() else cfg["price"]
        feats = "".join(f"<div style='color:#9CA3AF;font-size:0.82rem;margin:4px 0'>✓ {f}</div>" for f in cfg["features"])
        badge = (f"<div style='margin-top:14px;text-align:center;background:{cfg['color']}22;color:{cfg['color']};border:1px solid {cfg['color']}44;border-radius:6px;padding:4px;font-size:0.78rem;font-weight:700'>PLAN ACTUAL</div>" if is_current else "")
        with cols[i]:
            st.markdown(
                f"<div style='background:#1A1C23;border:2px solid {border_color};border-radius:12px;padding:20px;min-height:340px'>"
                f"<div style='font-size:2rem;text-align:center'>{cfg['emoji']}</div>"
                f"<h3 style='text-align:center;color:{cfg['color']};margin:8px 0 4px'>{cfg['label']}</h3>"
                f"<div style='text-align:center;font-size:1.6rem;font-weight:800;color:#FAFAFA;margin-bottom:12px'>{price_str}</div>"
                f"<hr style='border-color:#2D303E;margin:12px 0'>{feats}{badge}</div>",
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("Cambiar plan")
    btn_cols = st.columns(4)
    for i, (plan_key, cfg) in enumerate(PLAN_CONFIG.items()):
        plan_idx = PLAN_ORDER.index(plan_key)
        with btn_cols[i]:
            if plan_key == current_plan:
                st.markdown("<p style='text-align:center;color:#64748B;padding:8px 0'>Plan actual</p>", unsafe_allow_html=True)
            elif plan_key == "free":
                st.markdown("<p style='text-align:center;color:#64748B;padding:8px 0'>Gratis</p>", unsafe_allow_html=True)
            elif plan_key == "enterprise":
                st.link_button("Contactar →", "mailto:noahworkscuenca@gmail.com?subject=Plan%20Enterprise", use_container_width=True)
            else:
                label = f"Pasar a {cfg['label']}" if plan_idx > current_idx else f"Bajar a {cfg['label']}"
                if st.button(label, key=f"upgrade_{plan_key}", use_container_width=True):
                    url = _create_checkout_url(plan_key, user_email, user_id)
                    if url:
                        st.markdown(f'<meta http-equiv="refresh" content="0; url={url}">', unsafe_allow_html=True)
                    else:
                        st.warning("Stripe no está configurado. Agrega STRIPE_SECRET_KEY y STRIPE_PRICE_* a los secrets.")

    st.divider()
    if current_plan != "free":
        st.subheader("Gestionar suscripción")
        customer_id = None
        try:
            from supabase import create_client
            sb = create_client(os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", ""), os.getenv("SUPABASE_ANON_KEY") or st.secrets.get("SUPABASE_ANON_KEY", ""))
            res = sb.table("profiles").select("stripe_customer_id").eq("id", user_id).single().execute()
            customer_id = (res.data or {}).get("stripe_customer_id")
        except Exception:
            pass
        if st.button("U0001F517 Abrir portal de facturación Stripe"):
            portal_url = _create_portal_url(customer_id)
            if portal_url:
                st.markdown(f'<meta http-equiv="refresh" content="0; url={portal_url}">', unsafe_allow_html=True)
            else:
                st.warning("No se encontró suscripción activa.")
