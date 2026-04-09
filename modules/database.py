"""
modules/database.py — Cliente Supabase centralizado
"""

import os
import streamlit as st
from supabase import create_client, Client
from typing import Optional


@st.cache_resource
def get_supabase_client() -> Client:
    """Retorna cliente Supabase singleton (cacheado por sesión)."""
    url  = os.environ.get("SUPABASE_URL")
    key  = os.environ.get("SUPABASE_SERVICE_KEY")  # service_role para operaciones server-side
    if not url or not key:
        raise EnvironmentError(
            "Faltan SUPABASE_URL o SUPABASE_SERVICE_KEY en las variables de entorno. "
            "Revisa tu archivo .env"
        )
    return create_client(url, key)


def check_connection() -> bool:
    """Verifica que la conexión a Supabase sea exitosa."""
    try:
        db = get_supabase_client()
        db.table("invoice_categories").select("id").limit(1).execute()
        return True
    except Exception:
        return False


def paginate_query(table: str, filters: dict = None,
                   order_col: str = "created_at", ascending: bool = False,
                   page: int = 1, page_size: int = 20) -> dict:
    """
    Helper para consultas paginadas.
    Retorna: { 'data': [...], 'count': int, 'page': int, 'total_pages': int }
    """
    db = get_supabase_client()
    offset = (page - 1) * page_size

    query = db.table(table).select("*", count="exact")

    if filters:
        for col, val in filters.items():
            if val is not None:
                query = query.eq(col, val)

    query = query.order(order_col, desc=not ascending)
    query = query.range(offset, offset + page_size - 1)

    result = query.execute()
    total = result.count or 0
    total_pages = max(1, -(-total // page_size))  # ceil division

    return {
        "data": result.data or [],
        "count": total,
        "page": page,
        "total_pages": total_pages,
    }
