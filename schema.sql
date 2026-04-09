-- ============================================================
-- SCHEMA SUPABASE - GESTIÓN RESTAURANTE
-- Versión: 1.0 | Stack: PostgreSQL + Supabase
-- Estructura: suppliers → invoices → items → inventory → recipes
-- ============================================================

-- Extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- 1. PROVEEDORES
-- ============================================================
CREATE TABLE suppliers (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(200) NOT NULL,
    aliases         TEXT DEFAULT '',                     -- Nombres alternativos separados por coma (para mapeo OCR)
    ruc_nit         VARCHAR(50),                         -- RUC / NIT / RFC
    email           VARCHAR(150),
    phone           VARCHAR(30),
    address         TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- MIGRACIÓN: si la tabla ya existe, ejecutar en Supabase SQL Editor:
-- ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS aliases TEXT DEFAULT '';

COMMENT ON TABLE suppliers IS 'Catálogo maestro de proveedores del restaurante';

-- ============================================================
-- 2. CATEGORÍAS DE FACTURAS
-- ============================================================
CREATE TABLE invoice_categories (
    id          SMALLSERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,   -- Alimentos, Bebidas, Insumos, Servicios, Otros
    color_hex   VARCHAR(7) DEFAULT '#6B7280',   -- Para UI
    icon        VARCHAR(50)                     -- Nombre del ícono Streamlit
);

INSERT INTO invoice_categories (name, color_hex, icon) VALUES
    ('Alimentos',  '#10B981', 'food'),
    ('Bebidas',    '#3B82F6', 'drink'),
    ('Insumos',    '#F59E0B', 'package'),
    ('Servicios',  '#8B5CF6', 'wrench'),
    ('Otros',      '#6B7280', 'question');

-- ============================================================
-- 3. FACTURAS (núcleo del módulo de contabilidad)
-- ============================================================
CREATE TABLE invoices (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    supplier_id         UUID REFERENCES suppliers(id) ON DELETE RESTRICT,

    -- Datos extraídos por OCR / IA
    invoice_number      VARCHAR(100),
    invoice_date        DATE NOT NULL,
    category_id         SMALLINT REFERENCES invoice_categories(id),
    sale_type           VARCHAR(10) NOT NULL CHECK (sale_type IN ('CONTADO','CREDITO')),
    subtotal            NUMERIC(12, 2) DEFAULT 0,
    tax_amount          NUMERIC(12, 2) DEFAULT 0,
    total_amount        NUMERIC(12, 2) NOT NULL,
    currency            VARCHAR(3) DEFAULT 'USD',
    notes               TEXT,

    -- Metadatos jerárquicos para organización Año > Mes > Categoría
    fiscal_year         SMALLINT GENERATED ALWAYS AS (EXTRACT(YEAR FROM invoice_date)::SMALLINT) STORED,
    fiscal_month        SMALLINT GENERATED ALWAYS AS (EXTRACT(MONTH FROM invoice_date)::SMALLINT) STORED,

    -- Estado del ciclo de vida
    status              VARCHAR(20) DEFAULT 'PENDIENTE'
                            CHECK (status IN ('PENDIENTE','APROBADA','PAGADA','ANULADA')),
    due_date            DATE,                   -- Solo para crédito
    paid_at             TIMESTAMPTZ,            -- Timestamp cuando se marcó como pagada
    paid_by             UUID,                   -- FK a users (Supabase Auth)

    -- Imagen original
    image_url           TEXT,                   -- URL en Supabase Storage
    image_path          TEXT,                   -- Path interno en bucket

    -- Metadatos de procesamiento IA
    ocr_raw_response    JSONB,                  -- Respuesta completa de GPT-4 Vision
    ocr_confidence      NUMERIC(4,3),           -- 0.000 – 1.000
    ocr_processed_at    TIMESTAMPTZ,
    needs_review        BOOLEAN DEFAULT FALSE,  -- Flag para revisión manual

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para búsquedas frecuentes
CREATE INDEX idx_invoices_supplier    ON invoices(supplier_id);
CREATE INDEX idx_invoices_year_month  ON invoices(fiscal_year, fiscal_month);
CREATE INDEX idx_invoices_status      ON invoices(status);
CREATE INDEX idx_invoices_date        ON invoices(invoice_date DESC);
CREATE INDEX idx_invoices_category    ON invoices(category_id);

COMMENT ON TABLE invoices IS 'Registro central de facturas con datos extraídos por OCR/IA';
COMMENT ON COLUMN invoices.sale_type IS 'CONTADO = pago inmediato | CREDITO = genera cuenta por pagar';

-- ============================================================
-- 4. LÍNEAS DE FACTURA (ítems individuales)
-- ============================================================
CREATE TABLE invoice_items (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    invoice_id      UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    description     VARCHAR(300) NOT NULL,
    quantity        NUMERIC(10, 3) DEFAULT 1,
    unit            VARCHAR(30),               -- kg, litros, unidades, cajas...
    unit_price      NUMERIC(12, 4),
    line_total      NUMERIC(12, 2),
    product_id      UUID,                      -- FK a products (se resuelve post-OCR)
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_invoice_items_invoice ON invoice_items(invoice_id);
CREATE INDEX idx_invoice_items_product ON invoice_items(product_id);

-- ============================================================
-- 5. PRODUCTOS / INVENTARIO
-- ============================================================
CREATE TABLE products (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                VARCHAR(200) NOT NULL,
    sku                 VARCHAR(100) UNIQUE,
    category_id         SMALLINT REFERENCES invoice_categories(id),
    unit_of_measure     VARCHAR(30) DEFAULT 'unidad',  -- kg, litro, caja, unidad...
    current_stock       NUMERIC(12, 3) DEFAULT 0,
    min_stock           NUMERIC(12, 3) DEFAULT 0,      -- Umbral rojo (reorden urgente)
    reorder_point       NUMERIC(12, 3) DEFAULT 0,      -- Umbral amarillo (reabastecer pronto)
    max_stock           NUMERIC(12, 3),                -- Capacidad máxima de almacén
    unit_cost           NUMERIC(12, 4),                -- Último costo de compra
    loyverse_item_id    VARCHAR(100),                  -- ID del producto en Loyverse POS
    loyverse_variant_id VARCHAR(100),
    is_active           BOOLEAN DEFAULT TRUE,
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_products_loyverse  ON products(loyverse_item_id);
CREATE INDEX idx_products_category  ON products(category_id);
CREATE INDEX idx_products_sku       ON products(sku);

COMMENT ON TABLE products IS 'Catálogo de productos/insumos con control de stock';

-- ============================================================
-- 6. MOVIMIENTOS DE INVENTARIO (trazabilidad completa)
-- ============================================================
CREATE TABLE inventory_movements (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id      UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    movement_type   VARCHAR(20) NOT NULL
                        CHECK (movement_type IN ('ENTRADA','SALIDA','AJUSTE','MERMA')),
    quantity        NUMERIC(12, 3) NOT NULL,         -- Positivo = entrada, Negativo = salida
    stock_before    NUMERIC(12, 3),
    stock_after     NUMERIC(12, 3),
    unit_cost       NUMERIC(12, 4),
    reference_type  VARCHAR(30),                     -- 'INVOICE', 'LOYVERSE_SALE', 'MANUAL'
    reference_id    VARCHAR(100),                    -- ID de la factura o venta en Loyverse
    reference_date  DATE,
    notes           TEXT,
    created_by      UUID,                            -- FK Supabase Auth
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_movements_product    ON inventory_movements(product_id);
CREATE INDEX idx_movements_type       ON inventory_movements(movement_type);
CREATE INDEX idx_movements_date       ON inventory_movements(created_at DESC);
CREATE INDEX idx_movements_reference  ON inventory_movements(reference_type, reference_id);

-- ============================================================
-- 7. RECETAS / ESCANDALLOS
-- ============================================================
CREATE TABLE recipes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    loyverse_item_id VARCHAR(100),              -- Plato/producto en Loyverse POS
    yield_quantity  NUMERIC(8, 3) DEFAULT 1,    -- Rinde X porciones
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE recipe_items (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recipe_id       UUID NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    product_id      UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity        NUMERIC(10, 4) NOT NULL,    -- Cantidad por receta
    unit            VARCHAR(30),
    notes           TEXT
);

CREATE INDEX idx_recipe_items_recipe  ON recipe_items(recipe_id);
CREATE INDEX idx_recipe_items_product ON recipe_items(product_id);

-- ============================================================
-- 8. INTEGRACIÓN LOYVERSE (caché de sincronización)
-- ============================================================
CREATE TABLE loyverse_sync_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sync_type       VARCHAR(30) NOT NULL,       -- 'RECEIPTS', 'PRODUCTS', 'INVENTORY'
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    records_pulled  INTEGER DEFAULT 0,
    records_applied INTEGER DEFAULT 0,
    status          VARCHAR(20) DEFAULT 'RUNNING'
                        CHECK (status IN ('RUNNING','SUCCESS','FAILED')),
    error_message   TEXT,
    payload_summary JSONB
);

CREATE TABLE loyverse_sales (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    loyverse_receipt_id VARCHAR(100) UNIQUE NOT NULL,
    receipt_date        DATE NOT NULL,
    total_money         NUMERIC(12, 2),
    total_items         INTEGER,
    raw_data            JSONB,                  -- Payload completo del receipt
    inventory_applied   BOOLEAN DEFAULT FALSE,  -- ¿Ya se descontó del stock?
    applied_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_loyverse_sales_date     ON loyverse_sales(receipt_date DESC);
CREATE INDEX idx_loyverse_sales_applied  ON loyverse_sales(inventory_applied);

-- ============================================================
-- 9. VISTAS ÚTILES
-- ============================================================

-- Vista: Cuentas por Pagar (facturas de crédito pendientes)
CREATE VIEW v_accounts_payable AS
SELECT
    i.id,
    i.invoice_number,
    i.invoice_date,
    i.due_date,
    s.name                          AS supplier_name,
    ic.name                         AS category_name,
    ic.color_hex                    AS category_color,
    i.total_amount,
    i.currency,
    CURRENT_DATE - i.due_date       AS days_overdue,
    CASE
        WHEN i.due_date < CURRENT_DATE THEN 'VENCIDA'
        WHEN i.due_date <= CURRENT_DATE + 7 THEN 'POR_VENCER'
        ELSE 'AL_DIA'
    END                             AS payment_urgency,
    i.image_url,
    i.notes
FROM invoices i
JOIN suppliers s  ON s.id = i.supplier_id
JOIN invoice_categories ic ON ic.id = i.category_id
WHERE i.sale_type = 'CREDITO'
  AND i.status IN ('PENDIENTE','APROBADA')
ORDER BY i.due_date ASC NULLS LAST;

-- Vista: Estado de Stock con semáforo
CREATE VIEW v_stock_status AS
SELECT
    p.id,
    p.name,
    p.sku,
    ic.name                     AS category_name,
    p.unit_of_measure,
    p.current_stock,
    p.min_stock,
    p.reorder_point,
    p.max_stock,
    p.unit_cost,
    CASE
        WHEN p.current_stock <= p.min_stock     THEN 'ROJO'
        WHEN p.current_stock <= p.reorder_point THEN 'AMARILLO'
        ELSE                                         'VERDE'
    END                         AS stock_status,
    CASE
        WHEN p.current_stock <= p.min_stock     THEN '🔴 Stock Crítico'
        WHEN p.current_stock <= p.reorder_point THEN '🟡 Reabastecer Pronto'
        ELSE                                         '🟢 Stock OK'
    END                         AS status_label,
    p.loyverse_item_id,
    p.updated_at
FROM products p
LEFT JOIN invoice_categories ic ON ic.id = p.category_id
WHERE p.is_active = TRUE
ORDER BY
    CASE WHEN p.current_stock <= p.min_stock     THEN 1
         WHEN p.current_stock <= p.reorder_point THEN 2
         ELSE 3 END,
    p.name;

-- Vista: Resumen contable por Año/Mes/Categoría
CREATE VIEW v_accounting_summary AS
SELECT
    i.fiscal_year,
    i.fiscal_month,
    ic.name                         AS category_name,
    ic.color_hex,
    COUNT(*)                        AS invoice_count,
    SUM(i.total_amount)             AS total_amount,
    SUM(CASE WHEN i.sale_type = 'CONTADO' THEN i.total_amount ELSE 0 END) AS cash_total,
    SUM(CASE WHEN i.sale_type = 'CREDITO' THEN i.total_amount ELSE 0 END) AS credit_total,
    SUM(CASE WHEN i.status = 'PAGADA'     THEN i.total_amount ELSE 0 END) AS paid_total,
    SUM(CASE WHEN i.status IN ('PENDIENTE','APROBADA') AND i.sale_type = 'CREDITO'
             THEN i.total_amount ELSE 0 END) AS outstanding_total
FROM invoices i
JOIN invoice_categories ic ON ic.id = i.category_id
WHERE i.status != 'ANULADA'
GROUP BY i.fiscal_year, i.fiscal_month, ic.name, ic.color_hex
ORDER BY i.fiscal_year DESC, i.fiscal_month DESC, ic.name;

-- ============================================================
-- 10. FUNCIÓN: Auto-actualizar updated_at
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_suppliers_updated_at
    BEFORE UPDATE ON suppliers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_invoices_updated_at
    BEFORE UPDATE ON invoices
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_products_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- 11. FUNCIÓN: Registrar movimiento y actualizar stock atómicamente
-- ============================================================
CREATE OR REPLACE FUNCTION register_inventory_movement(
    p_product_id      UUID,
    p_movement_type   VARCHAR,
    p_quantity        NUMERIC,
    p_unit_cost       NUMERIC DEFAULT NULL,
    p_reference_type  VARCHAR DEFAULT NULL,
    p_reference_id    VARCHAR DEFAULT NULL,
    p_reference_date  DATE DEFAULT CURRENT_DATE,
    p_notes           TEXT DEFAULT NULL,
    p_created_by      UUID DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_stock_before  NUMERIC;
    v_stock_after   NUMERIC;
    v_movement_id   UUID;
    v_delta         NUMERIC;
BEGIN
    -- Calcular delta según tipo de movimiento
    v_delta := CASE
        WHEN p_movement_type IN ('ENTRADA') THEN ABS(p_quantity)
        WHEN p_movement_type IN ('SALIDA', 'MERMA') THEN -ABS(p_quantity)
        ELSE p_quantity  -- AJUSTE: puede ser positivo o negativo
    END;

    -- Obtener stock actual con lock
    SELECT current_stock INTO v_stock_before
    FROM products WHERE id = p_product_id FOR UPDATE;

    v_stock_after := v_stock_before + v_delta;

    -- No permitir stock negativo en salidas normales
    IF v_stock_after < 0 AND p_movement_type != 'AJUSTE' THEN
        RAISE EXCEPTION 'Stock insuficiente para producto %. Stock: %, Requerido: %',
            p_product_id, v_stock_before, ABS(p_quantity);
    END IF;

    -- Actualizar stock del producto
    UPDATE products
    SET current_stock = v_stock_after,
        unit_cost = COALESCE(p_unit_cost, unit_cost),
        updated_at = NOW()
    WHERE id = p_product_id;

    -- Registrar movimiento
    INSERT INTO inventory_movements (
        product_id, movement_type, quantity,
        stock_before, stock_after, unit_cost,
        reference_type, reference_id, reference_date,
        notes, created_by
    ) VALUES (
        p_product_id, p_movement_type, p_quantity,
        v_stock_before, v_stock_after, p_unit_cost,
        p_reference_type, p_reference_id, p_reference_date,
        p_notes, p_created_by
    ) RETURNING id INTO v_movement_id;

    RETURN v_movement_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- Row Level Security (RLS) - Base para multi-tenant futuro
-- ============================================================
ALTER TABLE invoices          ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice_items     ENABLE ROW LEVEL SECURITY;
ALTER TABLE products          ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory_movements ENABLE ROW LEVEL SECURITY;
ALTER TABLE suppliers         ENABLE ROW LEVEL SECURITY;

-- Policy permisiva inicial (autenticado = acceso total)
-- En producción: añadir columna restaurant_id y filtrar por organización
CREATE POLICY "authenticated_full_access" ON invoices
    FOR ALL USING (auth.role() = 'authenticated');
CREATE POLICY "authenticated_full_access" ON invoice_items
    FOR ALL USING (auth.role() = 'authenticated');
CREATE POLICY "authenticated_full_access" ON products
    FOR ALL USING (auth.role() = 'authenticated');
CREATE POLICY "authenticated_full_access" ON inventory_movements
    FOR ALL USING (auth.role() = 'authenticated');
CREATE POLICY "authenticated_full_access" ON suppliers
    FOR ALL USING (auth.role() = 'authenticated');
