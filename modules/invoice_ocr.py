"""
modules/invoice_ocr.py — Módulo de carga y clasificación de facturas
Usa Google Gemini API (nuevo SDK google-genai) para extracción estructurada de datos OCR.
Inventario: tabla 'products' + RPC register_inventory_movement.
Freemium: máximo 5 escaneos por día (cuenta via tabla 'invoices').
"""

import json
import re
import uuid
import os
from datetime import date, datetime
from io import BytesIO
from typing import Optional

# Palabras que no sirven para matching (stop words en español)
_STOP_WORDS = {
    "de", "del", "la", "el", "los", "las", "un", "una", "con", "sin",
    "por", "para", "en", "a", "y", "o", "al", "su", "sus", "kg", "gr",
    "lt", "ml", "oz", "lbs", "unidad", "unidades", "caja", "bolsa",
    "paquete", "galon", "gal", "litro", "litros", "kilo", "kilos",
}

# Límite diario de escaneos en plan gratuito
DAILY_SCAN_LIMIT = 5

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

# Inicializar cliente Gemini (singleton lazy)
_client: Optional["genai.Client"] = None  # type: ignore[name-defined]


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


# ── Freemium: contador de escaneos del día ───────────────────────────────────

def _count_today_invoices() -> int:
    """Cuenta las facturas escaneadas hoy (basado en created_at de la tabla invoices)."""
    try:
        db = get_supabase_client()
        today_str = date.today().isoformat()
        res = (
            db.table("invoices")
            .select("id", count="exact")
            .gte("created_at", today_str + "T00:00:00")
            .lte("created_at", today_str + "T23:59:59")
            .execute()
        )
        return res.count or 0
    except Exception:
        return 0


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
                alias_lines.append(
                    f'  - Si la factura dice {alias_options} → usar "{canonical}"'
                )

        if alias_lines:
            alias_block = (
                "\n\nREGLA CRÍTICA PARA supplier_name: Tenemos un diccionario de proveedores. "
                "Compara el nombre del emisor de la factura con estos alias y devuelve el nombre "
                "interno si hay coincidencia:\n"
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
    Convierte cualquier archivo (PDF o imagen) a JPEG comprimido.
    Garantiza que el resultado sea < 1 MB reduciendo calidad iterativamente.
    Retorna (jpeg_bytes, "image/jpeg").
    """
    MAX_PX       = 1024
    TARGET_BYTES = 900_000
    DPI_PDF      = 150

    if mime_type == "application/pdf":
        if not PYMUPDF_AVAILABLE:
            raise ImportError("PyMuPDF no instalado. Ejecuta: pip install PyMuPDF")
        doc  = fitz.open(stream=image_bytes, filetype="pdf")
        page = doc.load_page(0)
        pix  = page.get_pixmap(dpi=DPI_PDF)
        img  = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    else:
        img = Image.open(BytesIO(image_bytes))

    if img.mode != "RGB":
        img = img.convert("RGB")

    if max(img.size) > MAX_PX:
        img.thumbnail((MAX_PX, MAX_PX), Image.Resampling.LANCZOS)

    quality = 85
    while quality >= 40:
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        if buf.tell() <= TARGET_BYTES:
            break
        quality -= 10

    if buf.tell() > TARGET_BYTES:
        w, h = img.size
        img = img.resize((w // 2, h // 2), Image.Resampling.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=75)

    return buf.getvalue(), "image/jpeg"


# ── Extracción OCR principal ─────────────────────────────────────────────────

def extract_invoice_data(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """
    Comprime el archivo y lo envía a Google Gemini para extracción
    estructurada de datos de la factura.
    Retorna un dict con los campos extraídos o {"error": "..."} si falla.
    """
    raw_text = ""
    try:
        compressed_bytes, compressed_mime = _compress_for_gemini(image_bytes, mime_type)
        prompt = _build_prompt_with_aliases()

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
        db.storage.from_("invoices").upload(
            path=filename,
            file=image_bytes,
            file_options={
                "content-type": "application/pdf"
                if file_extension == "pdf"
                else f"image/{file_extension}"
            },
        )
        url_response = db.storage.from_("invoices").get_public_url(filename)
        return url_response
    except Exception as e:
        st.warning(f"No se pudo subir la imagen a Storage: {e}")
        return None


def save_invoice_to_db(
    ocr_data: dict,
    image_url: Optional[str],
    image_path: Optional[str],
) -> Optional[str]:
    """Persiste la factura y sus líneas de detalle en Supabase."""
    db = get_supabase_client()

    supplier_id    = _get_or_create_supplier(ocr_data.get("supplier_name"))
    category_name  = ocr_data.get("category", "Otros")
    category_id    = CATEGORY_MAP.get(category_name, 5)
    invoice_date   = ocr_data.get("invoice_date") or date.today().isoformat()
    due_date       = ocr_data.get("due_date")

    invoice_payload = {
        "supplier_id":      supplier_id,
        "invoice_number":   ocr_data.get("invoice_number"),
        "invoice_date":     invoice_date,
        "category_id":      category_id,
        "sale_type":        ocr_data.get("sale_type", "CONTADO").upper(),
        "subtotal":         ocr_data.get("subtotal"),
        "tax_amount":       ocr_data.get("tax_amount"),
        "total_amount":     ocr_data.get("total_amount", 0),
        "currency":         ocr_data.get("currency", "USD"),
        "due_date":         due_date,
        "status":           "PENDIENTE",
        "image_url":        image_url,
        "image_path":       image_path,
        "ocr_raw_response": {"raw": ocr_data.get("_raw_response")},
        "ocr_confidence":   ocr_data.get("confidence"),
        "ocr_processed_at": datetime.utcnow().isoformat(),
        "needs_review":     ocr_data.get("needs_review", False),
    }

    result = db.table("invoices").insert(invoice_payload).execute()

    if not result.data:
        return None

    invoice_id = result.data[0]["id"]

    # Guardar líneas de detalle
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
            for item in line_items
            if item.get("description")
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
    st.caption(
        "Sube una foto de tu factura física y la IA de Google extraerá los datos "
        "automáticamente."
    )

    # ── Verificar límite freemium ─────────────────────────────────────────────
    scans_today = _count_today_invoices()
    remaining   = max(0, DAILY_SCAN_LIMIT - scans_today)

    if scans_today >= DAILY_SCAN_LIMIT:
        st.error(
            f"🚫 **Límite diario alcanzado** — Has utilizado tus {DAILY_SCAN_LIMIT} escaneos "
            "gratuitos de hoy. El contador se reinicia a medianoche.",
            icon="🔒",
        )
        st.markdown(
            """
            <div style="background:linear-gradient(135deg,#6366F1,#8B5CF6);
                        border-radius:14px;padding:1.5rem 1.8rem;color:#fff;margin-top:1rem;">
                <p style="margin:0;font-size:1.1rem;font-weight:700">⚡ Actualiza a Pro</p>
                <p style="margin:0.4rem 0 0;font-size:0.9rem;opacity:0.9">
                    Con el plan Pro obtienes escaneos ilimitados, acceso prioritario a Gemini
                    y soporte dedicado para tu restaurante.
                </p>
                <p style="margin:0.8rem 0 0;font-size:0.8rem;opacity:0.75">
                    Contáctanos para activar tu cuenta Pro →
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    # Mostrar badge de uso del día
    badge_color = "#10B981" if remaining >= 3 else ("#F59E0B" if remaining >= 1 else "#EF4444")
    st.markdown(
        f"<span style='background:#F8FAFC;border:1px solid #E2E8F0;border-radius:20px;"
        f"padding:3px 12px;font-size:0.78rem;color:{badge_color};font-weight:600;'>"
        f"🆓 Plan gratuito · {remaining} escaneo(s) restante(s) hoy</span>",
        unsafe_allow_html=True,
    )
    st.write("")

    col_upload, col_preview = st.columns([1, 1], gap="large")

    with col_upload:
        st.subheader("1. Selecciona la imagen")

        uploaded_file = st.file_uploader(
            "📁 Sube la factura (JPG, PNG o PDF)",
            type=["jpg", "jpeg", "png", "pdf"],
            label_visibility="visible",
            help="Formatos admitidos: JPG, JPEG, PNG, PDF. Tamaño máximo recomendado: 10 MB.",
        )

        if uploaded_file:
            image_bytes = uploaded_file.read()
            mime_type   = uploaded_file.type or "image/jpeg"
            file_ext    = (
                uploaded_file.name.rsplit(".", 1)[-1].lower()
                if hasattr(uploaded_file, "name")
                else "jpg"
            )

            # ── Vista previa ─────────────────────────────────────────────────
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

            boton_label = (
                "⏳ Procesando..."
                if st.session_state["ocr_procesando"]
                else "🤖 Extraer datos con Google Gemini"
            )
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
                with st.spinner("Comprimiendo y analizando factura con IA…"):
                    try:
                        ocr_result = extract_invoice_data(image_bytes, mime_type)
                    except Exception as e:
                        st.error(f"❌ Error inesperado al llamar a Gemini: {e}")
                        st.session_state["ocr_procesando"] = False
                        return

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

        if st.session_state.get("ocr_result"):
            _render_ocr_review_form()


def _tokenize(text: str) -> set:
    """Extrae palabras útiles (>= 3 chars, sin stop words) de un texto."""
    words = set(re.findall(r'\b[a-záéíóúüñ]{3,}\b', text.lower()))
    return words - _STOP_WORDS


def _best_product_match(description: str, products: list) -> int:
    """
    Devuelve el índice en prod_options (0 = No actualizar) del mejor match
    entre la descripción OCR y los nombres de productos.
    Usa coincidencia exacta de subcadena primero, luego por palabras clave.
    """
    desc_lower = description.lower()
    desc_words = _tokenize(description)

    best_idx   = 0
    best_score = 0

    for j, prod in enumerate(products):
        name = prod["name"].lower()
        name_words = _tokenize(prod["name"])

        # Prioridad 1: coincidencia exacta de subcadena
        if name in desc_lower or desc_lower in name:
            return j + 1

        # Prioridad 2: score por palabras compartidas
        if desc_words and name_words:
            common = desc_words & name_words
            score = len(common) / max(len(name_words), 1)
            if score > best_score and score >= 0.5:
                best_score = score
                best_idx = j + 1

    return best_idx


def _update_products_from_items(line_items: list, products: list, invoice_id: Optional[str] = None) -> int:
    """
    Lee las selecciones de mapeo del session_state (claves prod_map_0, prod_map_1, …)
    y registra movimientos de ENTRADA vía register_inventory_movement RPC.
    Crea el producto si no existe aún.
    Retorna el número de productos actualizados.
    """
    db = get_supabase_client()
    prod_by_name = {p["name"]: p for p in products}
    updated = 0

    for idx, item in enumerate(line_items):
        selected = st.session_state.get(f"prod_map_{idx}", "— No actualizar —")
        if selected == "— No actualizar —":
            continue

        prod_name = selected.split(" (")[0].strip()
        prod_row  = prod_by_name.get(prod_name)

        qty = float(item.get("quantity") or 0)
        if qty <= 0:
            continue

        # Auto-crear producto si no existe
        if not prod_row:
            unit_ocr = item.get("unit") or "Unidades"
            new_prod = db.table("products").insert({
                "name":            prod_name,
                "unit_of_measure": unit_ocr,
                "current_stock":   0,
                "min_stock":       0,
                "reorder_point":   0,
                "is_active":       True,
            }).execute()
            if new_prod.data:
                prod_row = new_prod.data[0]
                prod_by_name[prod_name] = prod_row
            else:
                continue

        try:
            db.rpc("register_inventory_movement", {
                "p_product_id":      prod_row["id"],
                "p_movement_type":   "ENTRADA",
                "p_quantity":        qty,
                "p_unit_cost":       item.get("unit_price"),
                "p_reference_type":  "FACTURA",
                "p_reference_id":    invoice_id,
                "p_reference_date":  None,
                "p_notes":           f"OCR: {item.get('description', '')}",
                "p_created_by":      None,
            }).execute()
            updated += 1
        except Exception as e:
            st.warning(f"⚠️ No se pudo actualizar stock de '{prod_name}': {e}")

    return updated


def _render_ocr_review_form():
    """Formulario de revisión y confirmación de datos extraídos por OCR."""

    ocr = st.session_state["ocr_result"]

    # Cargar productos para el mapeo
    db = get_supabase_client()
    prod_res = (
        db.table("products")
        .select("id, name, unit_of_measure, current_stock")
        .eq("is_active", True)
        .order("name")
        .execute()
    )
    products      = prod_res.data or []
    prod_options  = ["— No actualizar —"] + [
        f"{p['name']} ({p['unit_of_measure']})" for p in products
    ]

    st.divider()
    st.subheader("3. Revisar y confirmar datos")

    if ocr.get("needs_review"):
        st.warning(
            "⚠️ La IA detectó algunos campos dudosos. "
            "Por favor revisa los datos antes de guardar."
        )

    confidence = ocr.get("confidence", 0)
    conf_color = (
        "green" if confidence >= 0.85
        else "orange" if confidence >= 0.6
        else "red"
    )
    st.markdown(
        f"Confianza OCR: "
        f"<span style='color:{conf_color};font-weight:700'>{confidence * 100:.0f}%</span>",
        unsafe_allow_html=True,
    )

    with st.form("invoice_confirm_form"):
        col1, col2 = st.columns(2)

        with col1:
            supplier_name  = st.text_input("Proveedor",         value=ocr.get("supplier_name") or "")
            invoice_number = st.text_input("Número de factura", value=ocr.get("invoice_number") or "")
            invoice_date   = st.date_input(
                "Fecha de factura",
                value=_parse_date(ocr.get("invoice_date")) or date.today(),
            )
            category = st.selectbox(
                "Categoría",
                ["Alimentos", "Bebidas", "Insumos", "Servicios", "Otros"],
                index=(
                    max(0, list(CATEGORY_MAP.keys()).index(ocr.get("category", "Otros")))
                    if ocr.get("category") in CATEGORY_MAP
                    else 4
                ),
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
            currency = st.text_input(
                "Moneda", value=ocr.get("currency") or "USD", max_chars=3
            )
            due_date = None
            if sale_type == "CREDITO":
                due_date = st.date_input(
                    "Fecha límite de pago",
                    value=_parse_date(ocr.get("due_date")) or date.today(),
                )

        notes = st.text_area("Notas adicionales", placeholder="Opcional…")

        # ── Mapeo líneas → Productos ─────────────────────────────────────────
        line_items = ocr.get("line_items") or []
        st.divider()

        if not line_items:
            st.warning(
                "⚠️ **La IA no detectó líneas individuales** en esta factura. "
                "El inventario NO se actualizará automáticamente. "
                "Si compraste ingredientes, agrégalos manualmente en **Inventario → Cargar Ingreso**."
            )
        else:
            auto_matches = sum(
                1 for item in line_items
                if _best_product_match(item.get("description", ""), products) > 0
            )
            no_matches = len(line_items) - auto_matches

            st.markdown(
                "<p style='font-weight:700;font-size:0.95rem;margin-bottom:0.2rem'>"
                "📦 4. Conectar con Inventario</p>",
                unsafe_allow_html=True,
            )

            if not products:
                st.info(
                    "ℹ️ No tienes productos en el inventario aún. "
                    "Puedes escribir el nombre del producto y se creará automáticamente al guardar."
                )

            if auto_matches > 0:
                st.success(
                    f"✅ {auto_matches} línea(s) emparejadas automáticamente con tu inventario."
                    + (f" · {no_matches} sin match — asígnalas manualmente si aplica." if no_matches else "")
                )
            else:
                st.warning(
                    "⚠️ Ninguna línea coincidió automáticamente con tus productos. "
                    "Selecciona manualmente el producto correspondiente para cada línea, "
                    "o deja '— No actualizar —' si no aplica."
                )

            st.caption(
                "Empareja cada línea de la factura con tu producto. "
                "La cantidad se sumará automáticamente al stock al guardar."
            )

            h1, h2, h3 = st.columns([3, 1, 3])
            h1.caption("**Línea en factura**")
            h2.caption("**Cantidad**")
            h3.caption("**→ Producto en inventario**")

            for idx, item in enumerate(line_items):
                desc = item.get("description", "")
                qty  = item.get("quantity", "")
                unit = item.get("unit", "")
                best = _best_product_match(desc, products)

                c1, c2, c3 = st.columns([3, 1, 3])
                c1.markdown(f"<small>{desc}</small>", unsafe_allow_html=True)
                c2.markdown(f"<small>**{qty}** {unit}</small>", unsafe_allow_html=True)
                c3.selectbox(
                    "prod",
                    options=prod_options,
                    index=best,
                    key=f"prod_map_{idx}",
                    label_visibility="collapsed",
                )

        submitted = st.form_submit_button(
            "💾 Guardar factura y actualizar inventario",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        with st.spinner("Guardando factura…"):
            try:
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
            except Exception as e:
                st.error(f"❌ Error al guardar la factura: {e}")
                return

        if invoice_id:
            n_updated = 0
            if line_items:
                with st.spinner("Actualizando inventario…"):
                    n_updated = _update_products_from_items(line_items, products, invoice_id)

            inv_msg = (
                f" · **{n_updated} producto(s) actualizados en inventario 📦**"
                if n_updated
                else (
                    " · ⚠️ Inventario no actualizado (sin líneas mapeadas). "
                    "Actualiza manualmente si es necesario."
                    if line_items
                    else ""
                )
            )
            st.success(f"✅ Factura guardada (ID: `({invoice_id[:8]|…) {inv_msg}")
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
