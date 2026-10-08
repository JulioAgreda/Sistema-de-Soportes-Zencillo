import streamlit as st
import db
from admin import es_admin, pagina_admin

st.set_page_config(page_title="Soporte Zencillo", page_icon="⛽", layout="centered")
st.title("Soporte Zencillo :red[Crítico]")

PAGINAS = [
    "🏠 Inicio", "🎫 Tickets", "📱 Dispositivos", "⚡ Respuestas Rápidas",
    "💬 Responder", "🗄️ Consultas SQL", "🎬 Videos Clientes",
    "📘 Manuales", "🔗 Enlaces", "🔐 Admin",
]
pagina = st.sidebar.radio("Menú", PAGINAS)
if es_admin():
    st.sidebar.success("Sesión de administrador activa")


def mostrar_snippets(categoria, con_ticket=False, lenguaje=None):
    admin = es_admin()  # el admin también ve los snippets sensibles
    buscar = st.text_input("🔍 Buscar", key=f"b_{categoria}").lower()
    ticket = st.text_input("N.º de ticket (reemplaza los **)", key=f"t_{categoria}") if con_ticket else ""
    items = [s for s in db.snippets(categoria, admin) if s["activo"]]
    if not items:
        st.info("Aún no hay contenido en esta categoría.")
    for s in items:
        if buscar and buscar not in s["titulo"].lower():
            continue
        texto = s["contenido"].replace("**", ticket) if ticket else s["contenido"]
        with st.expander(("🔒 " if s["sensible"] else "") + s["titulo"]):
            st.code(texto, language=lenguaje, wrap_lines=True)  # incluye botón de copiar


def mostrar_enlaces(tipo):
    items = [e for e in db.enlaces(tipo, es_admin()) if e["activo"]]
    for e in items:
        st.link_button(e["titulo"], e["url"], use_container_width=True)


if pagina == "🏠 Inicio":
    st.subheader("Escalamientos")
    for e in db.escalamientos():
        st.markdown(f"- **{e['area']}** → {e['responsable']}")
elif pagina == "🎫 Tickets":
    mostrar_snippets("Tickets", con_ticket=True)
elif pagina == "📱 Dispositivos":
    mostrar_snippets("Dispositivos", con_ticket=True)
elif pagina == "⚡ Respuestas Rápidas":
    mostrar_snippets("Respuestas Rápidas")
elif pagina == "💬 Responder":
    mostrar_snippets("Responder")
elif pagina == "🗄️ Consultas SQL":
    mostrar_snippets("Consultas SQL", lenguaje="sql")
elif pagina == "🎬 Videos Clientes":
    mostrar_snippets("Videos Clientes")
elif pagina == "📘 Manuales":
    mostrar_enlaces("manual")
elif pagina == "🔗 Enlaces":
    mostrar_enlaces("externo")
elif pagina == "🔐 Admin":
    pagina_admin()
