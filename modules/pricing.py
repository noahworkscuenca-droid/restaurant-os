import streamlit as st
import streamlit.components.v1 as components

def render_pricing_page():
    # 1. Encabezado limpio y directo
    st.markdown("""
        <div style="text-align: center; margin-bottom: 3rem;">
            <h1 style="font-size: 2.8rem; font-weight: 800; color: #FAFAFA; margin-bottom: 0.5rem;">Sube el nivel de tu Restaurante</h1>
            <p style="font-size: 1.1rem; color: #9CA3AF;">Automatiza la gestión, controla el inventario y ahorra horas de trabajo cada semana.</p>
        </div>
    """, unsafe_allow_html=True)

    # 2. Inyección de CSS avanzado para las tarjetas
    st.markdown("""
    <style>
    /* Estilo base de tarjeta */
    .pricing-card {
        background-color: #1A1C23;
        border: 1px solid #2D303E;
        border-radius: 16px;
        padding: 2.5rem 2rem;
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
        display: flex;
        flex-direction: column;
        height: 100%;
    }
    .pricing-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 20px rgba(0,0,0,0.2);
    }

    /* Plan Destacado (Premium) */
    .pricing-card.popular {
        border: 1px solid #4CAF50;
        background: linear-gradient(180deg, #1A2520 0%, #1A1C23 100%);
    }

    /* Etiqueta de "Más Popular" */
    .popular-badge {
        position: absolute;
        top: 0;
        right: 0;
        background-color: #4CAF50;
        color: #0E1117;
        font-size: 0.75rem;
        font-weight: 800;
        text-transform: uppercase;
        padding: 6px 16px;
        border-bottom-left-radius: 12px;
        letter-spacing: 0.5px;
    }

    /* Tipografía interior */
    .plan-name { font-size: 1.25rem; color: #FAFAFA; font-weight: 600; margin-bottom: 0.5rem; }
    .plan-price { font-size: 3rem; color: #FAFAFA; font-weight: 800; line-height: 1; margin-bottom: 0.2rem; }
    .plan-price span { font-size: 1rem; color: #9CA3AF; font-weight: 400; }
    .plan-desc { color: #9CA3AF; font-size: 0.9rem; margin-bottom: 2rem; line-height: 1.5; }

    /* Lista de beneficios */
    .feature-list { list-style: none; padding: 0; margin: 0 0 2rem 0; flex-grow: 1; }
    .feature-list li {
        color: #D1D5DB;
        font-size: 0.95rem;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
    }
    .feature-list li::before {
        content: "✓";
        color: #4CAF50;
        font-weight: bold;
        margin-right: 10px;
    }
    .feature-list li.disabled { color: #6B7280; }
    .feature-list li.disabled::before {
        content: "×";
        color: #6B7280;
    }
    </style>
    """, unsafe_allow_html=True)

    # 3. Construcción de las columnas (con un pequeño truco de espaciado)
    _, col1, col2, col3, _ = st.columns([0.2, 1, 1, 1, 0.2])

    # --- PLAN FREE ---
    with col1:
        st.markdown("""
        <div class="pricing-card">
            <div class="plan-name">Inicial</div>
            <div class="plan-price">$0<span>/mes</span></div>
            <div class="plan-desc">Para probar el sistema y digitalizar operaciones básicas.</div>
            <ul class="feature-list">
                <li>5 escaneos de facturas al día</li>
                <li>Gestión de inventario manual</li>
                <li>Dashboard financiero básico</li>
                <li class="disabled">Alertas de stock predictivas</li>
                <li class="disabled">Exportación de reportes</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        st.button("Tu Plan Actual", disabled=True, key="btn_free", use_container_width=True)

    # --- PLAN PREMIUM (Destacado) ---
    with col2:
        st.markdown("""
        <div class="pricing-card popular">
            <div class="popular-badge">Más Elegido</div>
            <div class="plan-name">Premium</div>
            <div class="plan-price">$17.99<span>/mes</span></div>
            <div class="plan-desc">Automatización total para restaurantes en crecimiento.</div>
            <ul class="feature-list">
                <li>Escaneo de facturas <b>Ilimitado</b></li>
                <li>Gestión de stock inteligente (IA)</li>
                <li>Dashboard financiero completo</li>
                <li>Alertas tempranas de stock</li>
                <li class="disabled">Soporte técnico 24/7</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        render_paypal_button("17.99", "Premium")

    # --- PLAN PRO ---
    with col3:
        st.markdown("""
        <div class="pricing-card">
            <div class="plan-name">Pro</div>
            <div class="plan-price">$29.99<span>/mes</span></div>
            <div class="plan-desc">Para operaciones complejas y múltiples sucursales.</div>
            <ul class="feature-list">
                <li>Todo lo del plan Premium</li>
                <li>Gestión Multi-Sucursal</li>
                <li>Sincronización avanzada con POS</li>
                <li>Reportes contables exportables</li>
                <li>Soporte técnico prioritario 24/7</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        render_paypal_button("29.99", "Pro")


def render_paypal_button(amount, plan_name):
    paypal_html = f"""
    <div id="paypal-button-container-{plan_name}"></div>
    <script src="https://www.paypal.com/sdk/js?client-id=sb&currency=USD"></script>
    <script>
        paypal.Buttons({{
            style: {{ layout: 'horizontal', color: 'blue', shape: 'rect', label: 'pay', height: 45 }},
            createOrder: function(data, actions) {{
                return actions.order.create({{
                    purchase_units: [{{
                        amount: {{ value: '{amount}' }},
                        description: 'Suscripción Divende OS - Plan {plan_name}'
                    }}]
                }});
            }},
            onApprove: function(data, actions) {{
                return actions.order.capture().then(function(details) {{
                    alert('¡Suscripción exitosa! Bienvenido al plan {plan_name}, ' + details.payer.name.given_name + '.');
                }});
            }}
        }}).render('#paypal-button-container-{plan_name}');
    </script>
    """
    components.html(paypal_html, height=60)
