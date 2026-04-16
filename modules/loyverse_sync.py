"""
modules/loyverse_sync.py — Sincronización de ventas desde la API de Loyverse.
Lee recibos del día, aplica las reglas de recetas y descuenta ingredientes
del inventario automáticamente.

Requiere: LOYVERSE_TOKEN en st.secrets (o .env)
DB columns usadas:
  inventory : ingredient_name, current_quantity
  recipes   : dish_name, ingredient, quantity, unit
"""

import streamlit as st
import requests
from datetime import datetime, timedelta

try:
    import pytz
    _UTC = pytz.utc
except ImportError:
    from datetime import timezone as _tz
    _UTC = _tz.utc


def render_sync_page():
    st.markdown(
        '<h3><i class="fas fa-sync-alt"></i> Sincronización de Caja (Loyverse)</h3>',
        unsafe_allow_html=True,
    )
    st.write("Extrae las ventas de hoy desde Loyverse y descuenta ingredientes del inventario.")

    # Importar supabase aquí para evitar import circular en el módulo
    from modules.database import get_supabase_client

    try:
        supabase = get_supabase_client()
    except Exception as e:
        st.error(f"No se pudo conectar a la base de datos: {e}")
        return

    if st.button("🚀 Sincronizar Ventas de Hoy", type="primary"):
        with st.spinner("Conectando con Loyverse..."):
            token = st.secrets.get("LOYVERSE_TOKEN") or ""
            if not token:
                st.error(
                    "Falta **LOYVERSE_TOKEN** en los secrets. "
                    "Agrégalo en Streamlit Cloud → Settings → Secrets."
                )
                return

            headers   = {"Authorization": f"Bearer {token}"}
            yesterday = (datetime.now(_UTC) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

            try:
                # 1. Obtener recibos de las últimas 24 horas
                url      = f"https://api.loyverse.com/v1.0/receipts?created_at_min={yesterday}"
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()
                receipts = response.json().get("receipts", [])

                if not receipts:
                    st.info("No hay ventas registradas en Loyverse en las últimas 24 horas.")
                    return

                # 2. Sumar cantidades por nombre de plato
                ventas: dict[str, float] = {}
                for receipt in receipts:
                    for item in receipt.get("line_items", []):
                        nombre = item.get("item_name", "").strip()
                        if nombre:
                            ventas[nombre] = ventas.get(nombre, 0.0) + float(item.get("quantity", 0))

                st.info(f"Se leyeron **{len(receipts)}** recibos con **{len(ventas)}** productos distintos.")

                # 3. Cargar reglas de recetas
                recetas_res = supabase.table("recipes").select("*").execute()
                recetas     = recetas_res.data or []

                if not recetas:
                    st.warning("No hay reglas de recetas configuradas. Ve a 🍳 Recetas para crearlas.")
                    return

                # 4. Descontar ingredientes
                descuentos: dict[str, float] = {}
                sin_regla:  list[str]        = []

                for plato, cant_vendida in ventas.items():
                    reglas_plato = [
                        r for r in recetas
                        if r.get("dish_name", "").lower() == plato.lower()
                    ]
                    if not reglas_plato:
                        sin_regla.append(plato)
                        continue

                    for regla in reglas_plato:
                        ingrediente   = regla.get("ingredient", "")
                        descuento_tot = float(regla.get("quantity") or 0) * cant_vendida

                        # Leer stock actual
                        stock_res = (
                            supabase.table("inventory")
                            .select("current_quantity")
                            .eq("ingredient_name", ingrediente)
                            .execute()
                        )
                        if not stock_res.data:
                            st.warning(f"Ingrediente **{ingrediente}** no encontrado en inventario.")
                            continue

                        stock_actual = float(stock_res.data[0].get("current_quantity") or 0)
                        nuevo_stock  = max(stock_actual - descuento_tot, 0.0)

                        supabase.table("inventory").update(
                            {"current_quantity": nuevo_stock}
                        ).eq("ingredient_name", ingrediente).execute()

                        descuentos[ingrediente] = descuentos.get(ingrediente, 0.0) + descuento_tot

                # 5. Mostrar resumen
                st.success("✅ ¡Inventario actualizado con éxito!")

                if descuentos:
                    st.markdown("**Ingredientes descontados:**")
                    rows = [
                        {"Ingrediente": k, "Cantidad descontada": round(v, 4)}
                        for k, v in descuentos.items()
                    ]
                    import pandas as pd
                    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
                else:
                    st.warning("Se leyeron ventas pero ninguna coincidió con las reglas de recetas.")

                if sin_regla:
                    st.info(
                        f"Los siguientes productos no tienen receta mapeada: "
                        f"{', '.join(sin_regla)}"
                    )

            except requests.exceptions.HTTPError as e:
                st.error(f"Error HTTP de Loyverse: {e.response.status_code} — {e.response.text[:200]}")
            except requests.exceptions.ConnectionError:
                st.error("No se pudo conectar con la API de Loyverse. Verifica tu conexión.")
            except Exception as e:
                st.error(f"Error inesperado: {e}")
