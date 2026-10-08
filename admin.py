"""Pestaña de administración: crear, editar, ocultar y eliminar contenido."""
import hmac
import streamlit as st
import db

MAX_INTENTOS = 5


def es_admin() -> bool:
    return st.session_state.get("admin", False)


def _login():
    st.subheader("🔐 Acceso de administrador")
    intentos = st.session_state.get("intentos", 0)
    if intentos >= MAX_INTENTOS:
        st.error("Demasiados intentos fallidos. Recarga la página para reintentar.")
        return
    with st.form("login"):
        clave = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            real = st.secrets["admin"]["password"]
            if hmac.compare_digest(clave.encode(), real.encode()):
                st.session_state["admin"] = True
                st.session_state["intentos"] = 0
                st.rerun()
            else:
                st.session_state["intentos"] = intentos + 1
                st.error("Contraseña incorrecta")


def _ejecutar(fn, *args, mensaje="Guardado ✅") -> bool:
    """Ejecuta una escritura; si sale bien deja un aviso para mostrarlo tras el rerun."""
    try:
        fn(*args)
    except Exception as e:  # p. ej. título duplicado (restricción unique)
        st.error(f"No se pudo completar la operación: {e}")
        return False
    st.session_state["flash"] = mensaje
    return True


# ---------------------------- SNIPPETS ----------------------------
def _tab_snippets():
    cats = db.categorias()
    cat = st.selectbox("Categoría", [c["nombre"] for c in cats])
    cat_id = next(c["id"] for c in cats if c["nombre"] == cat)
    items = db.snippets(cat, admin=True)

    with st.expander("➕ Nuevo snippet"):
        with st.form("nuevo_snippet", clear_on_submit=True):
            titulo = st.text_input("Título")
            contenido = st.text_area("Contenido", height=200,
                                     help="Usa ** donde debe ir el número de ticket.")
            c1, c2 = st.columns(2)
            orden = c1.number_input("Orden", 0, 999, len(items) + 1)
            sensible = c2.checkbox("🔒 Sensible (contiene credenciales)")
            if st.form_submit_button("Crear", type="primary"):
                if not titulo.strip() or not contenido.strip():
                    st.warning("Título y contenido son obligatorios.")
                elif _ejecutar(db.insertar, "snippets", {
                        "categoria_id": cat_id, "titulo": titulo.strip(),
                        "contenido": contenido, "orden": int(orden),
                        "sensible": sensible, "activo": True}, mensaje="Snippet creado ✅"):
                    st.rerun()

    buscar = st.text_input("🔍 Filtrar por título", key="adm_buscar").lower()
    for s in items:
        if buscar and buscar not in s["titulo"].lower():
            continue
        marca = ("🔒 " if s["sensible"] else "") + ("" if s["activo"] else "⏸️ ")
        with st.expander(f"{marca}{s['titulo']}"):
            with st.form(f"snip_{s['id']}"):
                titulo = st.text_input("Título", s["titulo"])
                contenido = st.text_area("Contenido", s["contenido"], height=220)
                c1, c2, c3 = st.columns(3)
                orden = c1.number_input("Orden", 0, 999, int(s["orden"] or 0))
                activo = c2.checkbox("Visible", s["activo"])
                sensible = c3.checkbox("🔒 Sensible", s["sensible"])
                confirmar = st.checkbox("Confirmo que quiero eliminarlo")
                b1, b2 = st.columns(2)
                guardar = b1.form_submit_button("💾 Guardar", type="primary")
                borrar = b2.form_submit_button("🗑️ Eliminar")
                if guardar:
                    if not titulo.strip() or not contenido.strip():
                        st.warning("Título y contenido son obligatorios.")
                    elif _ejecutar(db.actualizar, "snippets", s["id"], {
                            "titulo": titulo.strip(), "contenido": contenido,
                            "orden": int(orden), "activo": activo, "sensible": sensible}):
                        st.rerun()
                if borrar:
                    if not confirmar:
                        st.warning("Marca la casilla de confirmación para eliminar.")
                    elif _ejecutar(db.eliminar, "snippets", s["id"], mensaje="Eliminado 🗑️"):
                        st.rerun()


# ---------------------------- ENLACES ----------------------------
def _tab_enlaces():
    tipo = st.selectbox("Tipo", ["manual", "externo"],
                        format_func=lambda t: {"manual": "📘 Manuales", "externo": "🔗 Enlaces externos"}[t])
    items = db.enlaces(tipo, admin=True)

    with st.expander("➕ Nuevo enlace"):
        with st.form("nuevo_enlace", clear_on_submit=True):
            titulo = st.text_input("Título")
            url = st.text_input("URL (https://...)")
            if st.form_submit_button("Crear", type="primary"):
                if not titulo.strip() or not url.startswith(("http://", "https://")):
                    st.warning("Escribe un título y una URL que empiece por http(s)://")
                elif _ejecutar(db.insertar, "enlaces", {
                        "tipo": tipo, "titulo": titulo.strip(), "url": url.strip(),
                        "activo": True}, mensaje="Enlace creado ✅"):
                    st.rerun()

    for e in items:
        with st.expander(("" if e["activo"] else "⏸️ ") + e["titulo"]):
            with st.form(f"enl_{e['id']}"):
                titulo = st.text_input("Título", e["titulo"])
                url = st.text_input("URL", e["url"])
                activo = st.checkbox("Visible", e["activo"])
                confirmar = st.checkbox("Confirmo que quiero eliminarlo")
                b1, b2 = st.columns(2)
                if b1.form_submit_button("💾 Guardar", type="primary"):
                    if not titulo.strip() or not url.startswith(("http://", "https://")):
                        st.warning("Título obligatorio y URL con http(s)://")
                    elif _ejecutar(db.actualizar, "enlaces", e["id"], {
                            "titulo": titulo.strip(), "url": url.strip(), "activo": activo}):
                        st.rerun()
                if b2.form_submit_button("🗑️ Eliminar"):
                    if not confirmar:
                        st.warning("Marca la casilla de confirmación para eliminar.")
                    elif _ejecutar(db.eliminar, "enlaces", e["id"], mensaje="Eliminado 🗑️"):
                        st.rerun()


# ---------------------------- ESCALAMIENTOS ----------------------------
def _tab_escalamientos():
    with st.expander("➕ Nuevo escalamiento"):
        with st.form("nuevo_esc", clear_on_submit=True):
            area = st.text_input("Área / sistema")
            resp = st.text_input("Responsable")
            if st.form_submit_button("Crear", type="primary"):
                if not area.strip() or not resp.strip():
                    st.warning("Completa ambos campos.")
                elif _ejecutar(db.insertar, "escalamientos",
                               {"area": area.strip(), "responsable": resp.strip()},
                               mensaje="Escalamiento creado ✅"):
                    st.rerun()

    for e in db.escalamientos(admin=True):
        with st.expander(f"{e['area']} → {e['responsable']}"):
            with st.form(f"esc_{e['id']}"):
                area = st.text_input("Área / sistema", e["area"])
                resp = st.text_input("Responsable", e["responsable"])
                confirmar = st.checkbox("Confirmo que quiero eliminarlo")
                b1, b2 = st.columns(2)
                if b1.form_submit_button("💾 Guardar", type="primary"):
                    if not area.strip() or not resp.strip():
                        st.warning("Completa ambos campos.")
                    elif _ejecutar(db.actualizar, "escalamientos", e["id"],
                                   {"area": area.strip(), "responsable": resp.strip()}):
                        st.rerun()
                if b2.form_submit_button("🗑️ Eliminar"):
                    if not confirmar:
                        st.warning("Marca la casilla de confirmación para eliminar.")
                    elif _ejecutar(db.eliminar, "escalamientos", e["id"], mensaje="Eliminado 🗑️"):
                        st.rerun()


# ---------------------------- PÁGINA ----------------------------
def pagina_admin():
    if not es_admin():
        _login()
        return

    st.subheader("🛠️ Administración")
    if st.button("Cerrar sesión"):
        st.session_state["admin"] = False
        st.rerun()
    if msg := st.session_state.pop("flash", None):
        st.success(msg)

    t1, t2, t3 = st.tabs(["📝 Respuestas y consultas", "🔗 Enlaces y manuales", "📞 Escalamientos"])
    with t1:
        _tab_snippets()
    with t2:
        _tab_enlaces()
    with t3:
        _tab_escalamientos()
