"""Acceso a Supabase. Lectura pública con anon_key; escritura solo con service_key."""
import streamlit as st
from supabase import create_client

TABLAS_EDITABLES = {"snippets", "enlaces", "escalamientos"}


@st.cache_resource
def cliente(admin: bool = False):
    s = st.secrets["supabase"]
    return create_client(s["url"], s["service_key" if admin else "anon_key"])


# ---------------------------- LECTURA ----------------------------
@st.cache_data(ttl=300)
def categorias():
    return cliente().table("categorias").select("*").order("orden").execute().data


@st.cache_data(ttl=60)
def snippets(categoria: str, admin: bool = False):
    """Con admin=True devuelve también los inactivos y los sensibles."""
    cat = next((c for c in categorias() if c["nombre"] == categoria), None)
    if not cat:
        return []
    return (cliente(admin).table("snippets").select("*")
            .eq("categoria_id", cat["id"]).order("orden").execute().data)


@st.cache_data(ttl=60)
def enlaces(tipo: str, admin: bool = False):
    return (cliente(admin).table("enlaces").select("*")
            .eq("tipo", tipo).order("titulo").execute().data)


@st.cache_data(ttl=60)
def escalamientos(admin: bool = False):
    return cliente(admin).table("escalamientos").select("*").order("area").execute().data


# ---------------------------- ESCRITURA (solo admin) ----------------------------
def _tabla(nombre: str):
    if nombre not in TABLAS_EDITABLES:
        raise ValueError(f"Tabla no permitida: {nombre}")
    return cliente(admin=True).table(nombre)


def insertar(tabla: str, datos: dict):
    _tabla(tabla).insert(datos).execute()
    st.cache_data.clear()


def actualizar(tabla: str, id_: int, datos: dict):
    _tabla(tabla).update(datos).eq("id", id_).execute()
    st.cache_data.clear()


def eliminar(tabla: str, id_: int):
    _tabla(tabla).delete().eq("id", id_).execute()
    st.cache_data.clear()
