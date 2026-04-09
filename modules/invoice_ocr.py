"""
modules/invoice_ocr.py — Módulo de carga y clasificación de facturas
Usa Google Gemini API (nuevo SDK google-genai) para extracción estructurada de datos OCR.
"""

import json
import re
import uuid
import os
from datetime import date, datetime
from io import BytesIO
from typing import Optional

import streamlit as st
from PIL import Image

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# ── Nuevo SDK oficial de Google ──────────────────────────────────────────────
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

from modules.database import get_supabase_client

# Inicializar cliente con la API key
_API_KEY = os.getenv("GEMINI_API_KEY", "")
_client: Optional[genai.Client] = None

def _get_client():
    """Retorna el cliente Gemini (singleton)."""
    if not GENAI_AVAILABLE:
        raise ImportError(
            "Librería 'google-genai' no instalada. Ejecuta en tu terminal:\n"
            "python.exe -m pip install --upgrade google-genai"
        )
    global _client
    if _client is None:
        key = os.getenv("GEMINI_API_KEY", "")
        if not key:
            raise ValueError("GEMINI_API_KEY no encontrada en .env")
        _client = genai.Client(api_key=key)
    return _client


# ── Prompt de extracción OCR ─────────────────────────────────────────────────
OCR_SYSTEM_PROMPT = """Eres un asistente experto en contabilidad de restaurantes.
Analiza la imagen de una factura/ticket y extrae los datos en JSON con exactamente esta estructura.
Si un campo no está visible o es ilegible, usa null. Responde ÚNICAMENTE con el JSON, sin markdown.

{
  "supplier_name": "string — Nombre del proveedor/empresa emisora",
  "invoice_number": "string — Número de factura, ticket o recibo",
  "invoice_date": "YYYY-MM-DD — Fecha de la factura (ISO 8601)",
  "category": "string — UNO DE: Alimentos | Bebidas | Insumos | Servicios | Otros",
  "sale_type": "string — CONTADO o CREDITO (si no se indica, usar CONTADO)",
  "subtotal": "number — Subtotal antes de impuestos (null si no aparece)",
  "tax_amount": "number — Monto de impuesto (IVA/IGV/etc). null si no aparece",
  "total_amount": "number — Monto total a pagar (OBLIGATORIO)",
  "currency": "string — Código de moneda: USD, EUR, MXN, COP, etc.",
  "due_date": "YYYY-MM-DD — Fecha límite de pago si es crédito, null si es contado",
  "line_items": [
    {
      "description": "string",
      "quantity": "number",
      "unit": "string — kg/litros/unidad/caja/etc",
      "unit_price": "number",
      "line_total": "number"
    }
  ],
  "confidence": "number entre 0.0 y 1.0 — tu nivel de certeza en la extracción",
  "needs_review": "boolean — true si hay datos dudosos o ilegibles"
}"""

CATEGORY_MAP = {
    "Alimentos":  1,
    "Bebidas":    2,
    "Insumos":    3,
    "Servicios":  4,
    "Otros":      5,
}


def _build_prompt_with_aliases() -> str:
    """
    Construye el prompt OCR inyectando el diccionario de alias de proveedores
    desde Supabase. Si no hay alias configurados, retorna el prompt base.
    """
    try:
        db = get_supabase_client()
        result = db.table("suppliers").select("name, aliases").eq("is_active", True).execute()
        rows = result.data or []

        alias_lines = []
        for row in rows:
            canonical = row.get("name", "").strip()
            aliases_raw = row.get("aliases", "") or ""
            aliases = [a.strip() for a in aliases_raw.split(",") if a.strip()]
            if aliases:
                alias_options = " o ".join(f'"{a}"' for a in aliases)
                alias_lines.append(f'  - Si la factura dice {alias_options} → usar "{canonical}"')

        if alias_lines:
            alias_block = (
                "\n\nREGLA CRÍTICA PARA supplier_name: Tenemos un diccionario de proveedores. "
                "Compara el nombre del emisor de la factura con estos alias y devuelve el nombre interno si hay coincidencia:\n"
                + "\n".join(alias_lines)
                + "\n  - Si no coincide con ninguno, escribe el nombre exacto como aparece en la factura."
            )
            return OCR_SYSTEM_PROMPT + alias_block
    except Exception:
        pass

    return OCR_SYSTEM_PROMPT


# ── Compresión de imagen ─────────────────────────────────────────────────────

def _compress_for_gemini(image_bytes: bytes, mime_type: str) -> tuple[bytes, str]:
    """
    Convierte cualquier archivo (PDF o imagen) a JPEG comprimido ≤1024px.
    Retorna (jpeg_bytes, "image/jpeg").
    """
    MAX_PX  = 1024
    DPI_PDF = 150

    if mime_type == "application/pdf":
        if PYMUPDF_AVAILABLE:
            doc  = fitz.open(stream=image_bytes, filetype="pdf")
            page = doc.load_page(0)
            pix  = page.get_pixmap(dpi=DPI_PDF)
            img  = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        else:
            raise ImportError("PyMuPDF no instalado. Ejecuta: pip install PyMuPDF")
    else:
        img = Image.open(BytesIO(image_bytes))

    if img.mode != "RGB":
        img = img.convert("RGB")

    if max(img.size) > MAX_PX:
        img.thumbnail((MAX_PX, MAX_PX), Image.Resampling.LANCZOS)

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue(), "image/jpeg"


# ── Extracción OCR principal ─────────────────────────────────────────────────

def extract_invoice_data(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """
    Comprime el archivo y lo envía a Google Gemini para extracción estructurada.
    """
    raw_text = ""
    try:
        # Comprimir antes de enviar (ahorra tokens x20 en PDFs)
        compressed_bytes, compressed_mime = _compress_for_gemini(image_bytes, mime_type)

        prompt = _build_prompt_with_aliases()

        # Empaquetar imagen con el nuevo SDK
        image_part = types.Part.from_bytes(
            data=compressed_bytes,
            mime_type=compressed_mime,
        )

        client = _get_client()
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt, image_part],
        )

        raw_text = response.text.strip()

        # Limpiar markdown si Gemini lo añade
        raw_text = re.sub(r"^```[a-z]*\n?", "", raw_text)
        raw_text = re.sub(r"\n?```$", "", raw_text)

        data = json.loads(raw_text)
        data["_raw_response"] = raw_text
        return data

    except json.JSONDecodeError as e:
        return {"error": f"Respuesta IA no es JSON válido: {e}", "_raw_response": raw_text}
    except Exception as e:
        return {"error": str(e)}


def upload_invoice_image(image_bytes: bytes, file_extension: str = "jpg") -> Optional[str]:
    """Sube la imagen de la factura a Supabase Storage."""
    db = get_supabase_client()
    filename = f"invoices/{date.today().isoformat()}/{uuid.uuid4()}.{file_extension}"

    try:
        db.storage.from_("invoice-images").upload(
            path=filename,
            file=image_bytes,
            file_options={"content-type": "application/pdf" if file_extension == "pdf" else f"image/{file_extension}"},
        )
        url_response = db.storage.from_("invoice-images").get_public_url(filename)
        return url_response
    except Exception as e:
        st.warning(f"No se pudo subir la imagen a Storage: {e}")
        return None


def save_invoice_to_db(ocr_data: dict, image_url: Optional[str], image_path: Optional[str]) -> Optional[str]:
    """Persiste la factura y sus líneas en Supabase."""
    db = get_supabase_client()

    supplier_id  = _get_or_create_supplier(ocr_data.get("supplier_name"))
    category_name = ocr_data.get("category", "Otros")
    category_id   = CATEGORY_MAP.get(category_name, 5)
    invoice_date  = ocr_data.get("invoice_date") or date.today().isoformat()
    due_date       = ocr_data.get("due_date")

    invoice_payload = {
        "supplier_id":       supplier_id,
        "invoice_number":    ocr_data.get("invoice_number"),
        "invoice_date":      invoice_date,
        "category_id":       category_id,
        "sale_type":         ocr_data.get("sale_type", "CONTADO").upper(),
        "subtotal":          ocr_data.get("subtotal"),
        "tax_amount":        ocr_data.get("tax_amount"),
        "total_amount":      ocr_data.get("total_amount", 0),
        "currency":          ocr_data.get("currency", "USD"),
        "due_date":          due_date,
        "status":            "PENDIENTE",
        "image_url":         image_url,
        "image_path":        image_path,
        "ocr_raw_response":  {"raw": ocr_data.get("_raw_response")},
        "ocr_confidence":    ocr_data.get("confidence"),
        "ocr_processed_at":  datetime.utcnow().isoformat(),
        "needs_review":      ocr_data.get("needs_review", False),
    }

    result = db.table("invoices").insert(invoice_payload).execute()

    if not result.data:
        return None

    invoice_id = result.data[0]["id"]

    line_items = ocr_data.get("line_items") or []
    if line_items:
        items_payload = [
            {
                "invoice_id":  invoice_id,
                "description": item.get("description", ""),
                "quantity":    item.get("quantity"),
                "unit":        item.get("unit"),
                "unit_price":  item.get("unit_price"),
                "line_total":  item.get("line_total"),
            }
            for item in line_items if item.get("description")
        ]
        if items_payload:
            db.table("invoice_items").insert(items_payload).execute()

    return invoice_id


def _get_or_create_supplier(supplier_name: Optional[str]) -> Optional[str]:
    """Busca o crea el proveedor y retorna su UUID."""
    if not supplier_name:
        return None

    db = get_supabase_client()
    name_clean = supplier_name.strip()

    result = db.table("suppliers").select("id").ilike("name", name_clean).limit(1).execute()
    if result.data:
        return result.data[0]["id"]

    new_sup = db.table("suppliers").insert({"name": name_clean}).execute()
    return new_sup.data[0]["id"] if new_sup.data else None


# ── Página Streamlit: Subir y escanear factura ───────────────────────────────

def render_invoice_upload_page():
    """Renderiza la página principal de escaneo/carga de facturas."""

    st.title("📷 Escanear Factura")
    st.caption("Sube una foto de tu factura física y la IA de Google extraerá los datos automáticamente.")

    col_upload, col_preview = st.columns([1, 1], gap="large")

    with col_upload:
        st.subheader("1. Selecciona la imagen")

        upload_method = st.radio(
            "Método de carga",
            ["📁 Subir archivo", "📷 Cámara (móvil)"],
            horizontal=True,
            label_visibility="collapsed",
        )

        uploaded_file = None
        if upload_method == "📁 Subir archivo":
            uploaded_file = st.file_uploader(
                "Arrastra tu factura aquí",
                type=["jpg", "jpeg", "png", "webp", "heic", "pdf"],
                label_visibility="visible",
            )
        else:
            uploaded_file = st.camera_input("Toma una foto de la factura")

        if uploaded_file:
            image_bytes = uploaded_file.read()
            mime_type   = uploaded_file.type or "image/jpeg"
            file_ext    = uploaded_file.name.rsplit(".", 1)[-1].lower() if hasattr(uploaded_file, "name") else "jpg"

            # Vista previa
            with col_preview:
                st.subheader("Vista previa")
                if mime_type == "application/pdf":
                    size_kb = len(image_bytes) / 1024
                    st.markdown(
                        f"""<div style="background:#F8FAFC;border:2px dashed #CBD5E1;
                            border-radius:12px;padding:2.5rem 1rem;text-align:center;
                            color:#64748B;margin-top:0.5rem;">
                            <p style="font-size:3.5rem;margin:0">📄</p>
                            <p style="font-weight:700;color:#0F172A;margin:0.5rem 0 0.2rem;">
                                {uploaded_file.name}</p>
                            <p style="font-size:0.8rem;margin:0">
                                {size_kb:.1f} KB · PDF listo para analizar</p>
                        </div>""",
                        unsafe_allow_html=True,
                    )
                else:
                    img = Image.open(BytesIO(image_bytes))
                    st.image(img, use_container_width=True)

            st.divider()
            st.subheader("2. Procesar con IA")

            if "ocr_procesando" not in st.session_state:
                st.session_state["ocr_procesando"] = False

            boton_label = "⏳ Procesando..." if st.session_state["ocr_procesando"] else "🤖 Extraer datos con Google Gemini"
            boton = st.button(
                boton_label,
                type="primary",
                use_container_width=True,
                disabled=st.session_state["ocr_procesando"],
            )

            if boton:
                st.session_state["ocr_procesando"] = True
                st.rerun()

            if st.session_state["ocr_procesando"]:
                with st.spinner("Comprimiendo y analizando factura con IA..."):
                    ocr_result = extract_invoice_data(image_bytes, mime_type)

                st.session_state["ocr_procesando"] = False

                if "error" in ocr_result:
                    err_msg = str(ocr_result["error"])
                    if "429" in err_msg or "quota" in err_msg.lower():
                        st.warning(
                            "⏳ **Límite de la API alcanzado.** "
                            "Espera unos 30 segundos e intenta de nuevo.",
                            icon="🚦",
                        )
                    else:
                        st.error(f"❌ Error al procesar: {err_msg}")
                    return

                st.session_state["ocr_result"]  = ocr_result
                st.session_state["image_bytes"] = image_bytes
                st.session_state["mime_type"]   = mime_type
                st.session_state["file_ext"]    = file_ext

            if "ocr_result" in st.session_state and st.session_state["ocr_result"]:
                _render_ocr_review_form()


def _best_inventory_match(description: str, inventory_items: list) -> int:
    """
    Devuelve el índice en inv_options (0 = No actualizar) del mejor match
    entre la descripción OCR y los nombres de inventario.
    """
    desc_lower = description.lower()
    for j, inv in enumerate(inventory_items):
        ing = inv["ingredient_name"].lower()
        if ing in desc_lower or desc_lower in ing:
            return j + 1  # +1 porque índice 0 = "No actualizar"
    return 0


def _update_inventory_from_items(line_items: list, inventory_items: list) -> int:
    """
    Lee las selecciones de mapeo del session_state (claves inv_map_0, inv_map_1, …)
    y suma las cantidades OCR al inventario correspondiente.
    Retorna el número de ingredientes actualizados.
    """
    db = get_supabase_client()
    inv_by_name = {i["ingredient_name"]: i for i in inventory_items}
    updated = 0

    for idx, item in enumerate(line_items):
        selected = st.session_state.get(f"inv_map_{idx}", "— No actualizar —")
        if selected == "— No actualizar —":
            continue

        # El label tiene formato "Nombre (unidad)"
        ing_name = selected.split(" (")[0].strip()
        inv_row  = inv_by_name.get(ing_name)
        if not inv_row:
            continue

        qty = float(item.get("quantity") or 0)
        if qty <= 0:
            continue

        new_qty = float(inv_row.get("current_quantity") or 0) + qty
        db.table("inventory").update({
            "current_quantity": new_qty,
            "updated_at": "now()",
        }).eq("id", inv_row["id"]).execute()

        # Actualizar el cache local para si hay duplicados en la factura
        inv_by_name[ing_name]["current_quantity"] = new_qty
        updated += 1

    return updated


def _render_ocr_review_form():
    """Formulario de revisión y confirmación de datos extraídos por OCR."""

    ocr = st.session_state["ocr_result"]

    # Cargar inventario para el mapeo (fuera del form para no bloquear la cache)
    db = get_supabase_client()
    inv_res = db.table("inventory").select("id, ingredient_name, unit, current_quantity") \
                .order("ingredient_name").execute()
    inventory_items = inv_res.data or []
    inv_options = ["— No actualizar —"] + [
        f"{i['ingredient_name']} ({i['unit']})" for i in inventory_items
    ]

    st.divider()
    st.subheader("3. Revisar y confirmar datos")

    if ocr.get("needs_review"):
        st.warning("⚠️ La IA detectó algunos campos dudosos. Por favor revisa los datos antes de guardar.")

    confidence = ocr.get("confidence", 0)
    conf_color = "green" if confidence >= 0.85 else "orange" if confidence >= 0.6 else "red"
    st.markdown(
        f"Confianza OCR: <span style='color:{conf_color};font-weight:700'>{confidence*100:.0f}%</span>",
        unsafe_allow_html=True,
    )

    with st.form("invoice_confirm_form"):
        col1, col2 = st.columns(2)

        with col1:
            supplier_name  = st.text_input("Proveedor",        value=ocr.get("supplier_name") or "")
            invoice_number = st.text_input("Número de factura", value=ocr.get("invoice_number") or "")
            invoice_date   = st.date_input(
                "Fecha de factura",
                value=_parse_date(ocr.get("invoice_date")) or date.today(),
            )
            category = st.selectbox(
                "Categoría",
                ["Alimentos", "Bebidas", "Insumos", "Servicios", "Otros"],
                index=max(0, list(CATEGORY_MAP.keys()).index(ocr.get("category", "Otros")))
                      if ocr.get("category") in CATEGORY_MAP else 4,
            )

        with col2:
            sale_type = st.selectbox(
                "Tipo de venta",
                ["CONTADO", "CREDITO"],
                index=0 if ocr.get("sale_type", "CONTADO").upper() == "CONTADO" else 1,
            )
            total_amount = st.number_input(
                "Monto total",
                value=float(ocr.get("total_amount") or 0),
                min_value=0.0,
                format="%.2f",
            )
            currency = st.text_input("Moneda", value=ocr.get("currency") or "USD", max_chars=3)
            due_date = None
            if sale_type == "CREDITO":
                due_date = st.date_input(
                    "Fecha límite de pago",
                    value=_parse_date(ocr.get("due_date")) or date.today(),
                )

        notes = st.text_area("Notas adicionales", placeholder="Opcional...")

        # ── Paso 4: Mapeo de líneas → Inventario ─────────────────────────────
        line_items = ocr.get("line_items") or []
        if line_items:
            st.divider()
            st.markdown(
                "<p style='font-weight:700;font-size:0.95rem;margin-bottom:0.2rem'>"
                "📦 4. Conectar con Inventario</p>"
                "<p style='font-size:0.8rem;color:#64748B;margin-top:0;'>"
                "Empareja cada línea de la factura con tu ingrediente. "
                "La cantidad se sumará automáticamente al stock.</p>",
                unsafe_allow_html=True,
            )

            # Encabezados de columna
            h1, h2, h3 = st.columns([3, 1, 3])
            h1.caption("**Línea en factura**")
            h2.caption("**Cantidad**")
            h3.caption("**→ Ingrediente en inventario**")

            for idx, item in enumerate(line_items):
                desc = item.get("description", "")
                qty  = item.get("quantity", "")
                unit = item.get("unit", "")
                best = _best_inventory_match(desc, inventory_items)

                c1, c2, c3 = st.columns([3, 1, 3])
                c1.markdown(f"<small>{desc}</small>", unsafe_allow_html=True)
                c2.markdown(f"<small>**{qty}** {unit}</small>", unsafe_allow_html=True)
                c3.selectbox(
                    "inv",
                    options=inv_options,
                    index=best,
                    key=f"inv_map_{idx}",
                    label_visibility="collapsed",
                )

        submitted = st.form_submit_button("💾 Guardar factura y actualizar inventario", type="primary", use_container_width=True)

    if submitted:
        with st.spinner("Guardando factura..."):
            image_url = upload_invoice_image(
                st.session_state["image_bytes"],
                st.session_state.get("file_ext", "jpg"),
            )

            final_data = {
                **ocr,
                "supplier_name":  supplier_name,
                "invoice_number": invoice_number,
                "invoice_date":   invoice_date.isoformat(),
                "category":       category,
                "sale_type":      sale_type,
                "total_amount":   total_amount,
                "currency":       currency,
                "due_date":       due_date.isoformat() if due_date else None,
                "_notes":         notes,
            }

            invoice_id = save_invoice_to_db(final_data, image_url, None)

        if invoice_id:
            # Actualizar inventario con las cantidades mapeadas
            n_updated = 0
            if line_items and inventory_items:
                with st.spinner("Actualizando inventario..."):
                    n_updated = _update_inventory_from_items(line_items, inventory_items)

            st.success(
                f"✅ Factura guardada (ID: `{invoice_id[:8]}...`)"
                + (f" · **{n_updated} ingrediente(s) actualizados** en inventario 📦" if n_updated else "")
            )
            for key in ["ocr_result", "image_bytes", "mime_type", "file_ext"]:
                st.session_state.pop(key, None)
            st.balloons()
        else:
            st.error("Error al guardar la factura. Intenta de nuevo.")


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    """Parsea una fecha ISO 8601 o retorna None."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
