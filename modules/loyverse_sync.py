import streamlit as st
import pandas as pd
from modules.database import get_supabase_client

def render_sync_page():
    st.markdown("## 🔄 Sincronización Loyverse (Cierre de Turno)")
    st.caption("Sube el archivo CSV de ventas diarias para actualizar el inventario automáticamente.")

    # 1. El Uploader
    uploaded_file = st.file_uploader("📂 Sube el archivo 'Ventas_por_articulo.csv'", type=["csv"])

    if uploaded_file is not None:
        try:
            # 2. Leer y limpiar el CSV de Loyverse
            df_ventas = pd.read_csv(uploaded_file)

            # Loyverse a veces trae columnas extrañas, nos aseguramos de tener lo básico
            columnas_esperadas = ["Articulo", "Categoria", "Articulos vendidos"]
            if not all(col in df_ventas.columns for col in columnas_esperadas):
                st.error("⚠️ El formato del archivo no es correcto. Asegúrate de descargar el reporte de 'Ventas por artículo'.")
                return

            # Filtramos solo lo que realmente se vendió (ignoramos devoluciones si las hay)
            df_ventas = df_ventas[df_ventas["Articulos vendidos"] > 0]

            # Mostrar resumen
            st.success(f"✅ Archivo leído correctamente. Se encontraron {len(df_ventas)} platos/productos vendidos.")

            with st.expander("Ver detalle del cierre de ventas"):
                st.dataframe(df_ventas[["Articulo", "Categoria", "Articulos vendidos"]], use_container_width=True)

            # 3. El botón de Acción (El descuento real)
            if st.button("🔽 Procesar Ventas y Descontar Inventario", type="primary", use_container_width=True):
                with st.spinner("Cruzando ventas con escandallos (recetas)..."):
                    db = get_supabase_client()

                    # A. Obtener todas las recetas/escandallos
                    res_recetas = db.table("recipes").select("*").execute()
                    recetas = res_recetas.data

                    if not recetas:
                        st.warning("No tienes recetas configuradas. El sistema no sabe qué ingredientes descontar.")
                        return

                    mapa_recetas = {}
                    for r in recetas:
                        plato = r["dish_name"]
                        if plato not in mapa_recetas:
                            mapa_recetas[plato] = []
                        mapa_recetas[plato].append({
                            "ingrediente": r["ingredient"],
                            "cantidad": r["quantity"]
                        })

                    # B. Calcular el consumo total de ingredientes
                    consumo_total = {}

                    for index, row in df_ventas.iterrows():
                        plato_vendido = row["Articulo"]
                        cantidad_vendida = float(row["Articulos vendidos"])

                        if plato_vendido in mapa_recetas:
                            for ingrediente in mapa_recetas[plato_vendido]:
                                nombre_ing = ingrediente["ingrediente"]
                                qty_necesaria = float(ingrediente["cantidad"]) * cantidad_vendida
                                consumo_total[nombre_ing] = consumo_total.get(nombre_ing, 0) + qty_necesaria

                    # C. Ejecutar los descuentos en Supabase
                    items_actualizados = 0
                    for ingrediente, cantidad_a_descontar in consumo_total.items():
                        try:
                            prod_res = db.table("products").select("id").ilike("name", ingrediente).limit(1).execute()
                            if not prod_res.data:
                                st.warning(f"⚠️ Producto '{ingrediente}' no encontrado en inventario — omitido.")
                                continue
                            prod_id = prod_res.data[0]["id"]

                            db.rpc("register_inventory_movement", {
                                "p_product_id":     prod_id,
                                "p_movement_type":  "SALIDA_VENTA",
                                "p_quantity":       -abs(cantidad_a_descontar),
                                "p_unit_cost":      None,
                                "p_reference_type": "LOYVERSE",
                                "p_reference_id":   None,
                                "p_reference_date": None,
                                "p_notes":          f"Cierre de turno: {ingrediente}",
                                "p_created_by":     None,
                            }).execute()
                            items_actualizados += 1
                        except Exception as e:
                            st.error(f"Error al descontar {ingrediente}: {e}")

                    st.success(f"🎉 ¡Cierre exitoso! Se descontaron {items_actualizados} ingredientes del inventario base.")
                    st.balloons()

        except Exception as e:
            st.error(f"Error al procesar el archivo: {e}")
