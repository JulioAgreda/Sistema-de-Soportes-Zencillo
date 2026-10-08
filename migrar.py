"""
migrar.py - Migra el contenido de tus HTML de Soporte Zencillo a Supabase.

USO
    # 1) Vista previa (NO escribe nada, genera migracion_preview.json)
    python migrar.py --carpeta ./html

    # 2) Cargar a Supabase
    python migrar.py --carpeta ./html --apply

La carpeta debe contener: index.html, Res_Rapidas.html, consultas.html,
Manuales.html y (si lo tienes) videosClientes.html.

CREDENCIALES (solo para --apply)
    Usa la service_key (NO la anon_key), porque la escritura está bloqueada
    por RLS para la clave pública. Se lee de:
      - variables de entorno SUPABASE_URL y SUPABASE_SERVICE_KEY, o
      - .streamlit/secrets.toml  ->  [supabase] url / service_key

ANTES DE EJECUTAR con --apply, corre este SQL una sola vez en Supabase
(hace que el script sea re-ejecutable sin duplicar datos):

    alter table snippets add constraint snippets_cat_titulo_uq unique (categoria_id, titulo);
    alter table enlaces  add constraint enlaces_tipo_titulo_uq unique (tipo, titulo);
    alter table escalamientos add constraint escalamientos_area_uq unique (area);
"""
import argparse
import json
import os
import re
import sys
import textwrap
from pathlib import Path

from bs4 import BeautifulSoup

# --------------------------------------------------------------------------
# Correcciones puntuales detectadas en el análisis (se reportan al ejecutar)
# --------------------------------------------------------------------------
CORRECCIONES_TITULO = {
    "Resuesta 2 (Soporte)": "Respuesta 2 (Soporte)",
}
CORRECCIONES_CONTENIDO = {
    "select from descuento": "select * from descuento",   # faltaba el *
    "Sunmy": "Sunmi",
}
# Avisos que NO se corrigen solos (hay que decidirlos tú)
AVISOS = [
    ("abierto=11", "cc_9 'Ver estado de Turno empleado': ¿debería ser abierto=1?"),
    ("'2026-8-15'", "cc_2/cc_3: fechas fijas en la consulta; reemplázalas cuando las uses."),
]

# Solo marca como sensible si hay una contraseña con valor (ej. "*Contraseña:* 123")
PATRON_SENSIBLE = re.compile(r"(contrase[ñn]a|password)\s*:?\*?\s*:?\s*\S+\s*$", re.I | re.M)


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------
def limpiar(texto: str) -> str:
    """Quita la sangría que arrastran los <p> multilínea del HTML."""
    lineas = texto.replace("\r", "").split("\n")
    primera = lineas[0].strip()
    resto = textwrap.dedent("\n".join(lineas[1:])).rstrip() if len(lineas) > 1 else ""
    resto = "\n".join(l.rstrip() for l in resto.split("\n"))
    return (primera + ("\n" + resto if resto.strip() else "")).strip()


def aplicar_correcciones(texto: str, reporte: list) -> str:
    for malo, bueno in CORRECCIONES_CONTENIDO.items():
        if malo in texto:
            texto = texto.replace(malo, bueno)
            reporte.append(f"Corregido: '{malo}' -> '{bueno}'")
    return texto


def leer(carpeta: Path, nombre: str):
    ruta = carpeta / nombre
    if not ruta.exists():
        print(f"  ! No se encontró {nombre} (se omite)")
        return None
    return BeautifulSoup(ruta.read_text(encoding="utf-8"), "html.parser")


def ids_en_onclick(tag, funcion_regex=r"copiar\w+"):
    m = re.search(rf"{funcion_regex}\('([^']+)'", tag.get("onclick", ""))
    return m.group(1) if m else None


# --------------------------------------------------------------------------
# Extractores
# --------------------------------------------------------------------------
def extraer_menu(soup, reporte):
    """Tickets (rpt_) y Dispositivos (rpd_): el título sale del texto del menú."""
    titulos = {}
    for a in soup.select(".menu_vertical a[onclick]"):
        id_ = ids_en_onclick(a)
        if id_:
            titulos[id_] = a.get_text(strip=True)

    out = []
    for p in soup.select(".respuestas-ocultas p[id]"):
        id_ = p["id"]
        if id_.startswith("rpt_"):
            cat = "Tickets"
        elif id_.startswith("rpd_"):
            cat = "Dispositivos"
        else:
            continue
        contenido = aplicar_correcciones(limpiar(p.get_text()), reporte)
        out.append({
            "categoria": cat,
            "titulo": titulos.get(id_, id_),
            "contenido": contenido,
            "orden": int(id_.split("_")[1]),
            "sensible": bool(PATRON_SENSIBLE.search(contenido)),
        })
    return out


def extraer_tarjetas(soup, prefijo, categoria, reporte, funcion=r"copiarConsulta"):
    """Tarjetas .link-card con su <p id=prefijo_N> asociado."""
    out, vacias = [], 0
    for orden, card in enumerate(soup.select(".link-card[onclick]"), start=1):
        id_ = ids_en_onclick(card, funcion)
        if not id_ or not id_.startswith(prefijo):
            continue
        titulo = card.select_one(".link-title").get_text(strip=True)
        p = soup.find("p", id=id_)
        contenido = limpiar(p.get_text()) if p else ""
        if not titulo or not contenido:
            vacias += 1
            continue
        titulo = CORRECCIONES_TITULO.get(titulo, titulo)
        contenido = aplicar_correcciones(contenido, reporte)
        out.append({
            "categoria": categoria,
            "titulo": titulo,
            "contenido": contenido,
            "orden": orden,
            "sensible": bool(PATRON_SENSIBLE.search(contenido)),
        })
    if vacias:
        reporte.append(f"{categoria}: {vacias} tarjeta(s) sin título o sin contenido omitidas")
    return out


def extraer_manuales(soup):
    return [
        {"tipo": "manual",
         "titulo": a.select_one(".link-title").get_text(strip=True),
         "url": a["href"].strip()}
        for a in soup.select("a.link-card[href]")
    ]


def extraer_externos(soup):
    return [
        {"tipo": "externo", "titulo": a.get_text(strip=True), "url": a["href"].strip()}
        for a in soup.select(".menu_vertical a[target=_blank][href]")
    ]


def extraer_escalamientos(soup):
    out = []
    main = soup.find("main")
    if not main:
        return out
    for li in main.select("ul > li"):
        txt = li.get_text(strip=True)
        if "->" in txt:
            area, resp = [x.strip() for x in txt.split("->", 1)]
            out.append({"area": area, "responsable": resp})
    return out


# --------------------------------------------------------------------------
# Supabase
# --------------------------------------------------------------------------
def credenciales():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not (url and key):
        ruta = Path(".streamlit/secrets.toml")
        if ruta.exists():
            import tomllib
            s = tomllib.loads(ruta.read_text(encoding="utf-8")).get("supabase", {})
            url, key = s.get("url"), s.get("service_key")
    if not (url and key):
        sys.exit("Faltan credenciales: define SUPABASE_URL y SUPABASE_SERVICE_KEY "
                 "o completa .streamlit/secrets.toml")
    return url, key


def cargar(datos):
    from supabase import create_client
    db = create_client(*credenciales())

    # Categorías (orden fijo)
    nombres = ["Tickets", "Dispositivos", "Respuestas Rápidas", "Consultas SQL",
               "Responder", "Videos Clientes"]
    db.table("categorias").upsert(
        [{"nombre": n, "orden": i} for i, n in enumerate(nombres, 1)],
        on_conflict="nombre").execute()
    ids = {c["nombre"]: c["id"] for c in db.table("categorias").select("id,nombre").execute().data}

    filas = [{"categoria_id": ids[s["categoria"]], "titulo": s["titulo"],
              "contenido": s["contenido"], "orden": s["orden"], "sensible": s["sensible"]}
             for s in datos["snippets"]]
    if filas:
        db.table("snippets").upsert(filas, on_conflict="categoria_id,titulo").execute()
    if datos["enlaces"]:
        db.table("enlaces").upsert(datos["enlaces"], on_conflict="tipo,titulo").execute()
    if datos["escalamientos"]:
        db.table("escalamientos").upsert(datos["escalamientos"], on_conflict="area").execute()


# --------------------------------------------------------------------------
# Principal
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--carpeta", default=".", help="Carpeta con los HTML")
    ap.add_argument("--apply", action="store_true", help="Escribir en Supabase (sin esto solo es vista previa)")
    args = ap.parse_args()
    carpeta = Path(args.carpeta)
    reporte = []

    datos = {"snippets": [], "enlaces": [], "escalamientos": []}

    print("Leyendo archivos...")
    if (s := leer(carpeta, "index.html")):
        datos["snippets"] += extraer_menu(s, reporte)
        datos["snippets"] += extraer_tarjetas(s, "rp_", "Responder", reporte)
        datos["enlaces"] += extraer_externos(s)
        datos["escalamientos"] += extraer_escalamientos(s)
    if (s := leer(carpeta, "Res_Rapidas.html")):
        datos["snippets"] += extraer_tarjetas(s, "rr_", "Respuestas Rápidas", reporte)
    if (s := leer(carpeta, "consultas.html")):
        datos["snippets"] += extraer_tarjetas(s, "cc_", "Consultas SQL", reporte)
    if (s := leer(carpeta, "Manuales.html")):
        datos["enlaces"] += extraer_manuales(s)
    if (s := leer(carpeta, "videosClientes.html")):
        # Las tarjetas copian un texto "*TÍTULO:* url", así que se guardan como snippets
        datos["snippets"] += extraer_tarjetas(s, "vpc_", "Videos Clientes", reporte)

    # Avisos de revisión manual
    todo = " ".join(x["contenido"] for x in datos["snippets"])
    for patron, aviso in AVISOS:
        if patron in todo:
            reporte.append("Revisar: " + aviso)
    for s in datos["snippets"]:
        if s["sensible"]:
            reporte.append(f"Marcado como SENSIBLE (solo visible con service key): '{s['titulo']}'")

    # Títulos duplicados dentro de una categoría (rompen el upsert) y URLs repetidas
    vistos = {}
    for sn in datos["snippets"]:
        k = (sn["categoria"], sn["titulo"])
        if k in vistos:
            reporte.append(f"TÍTULO DUPLICADO en {k[0]}: '{k[1]}' (renómbralo en el HTML antes de --apply)")
        vistos[k] = True
    urls = {}
    for sn in datos["snippets"]:
        if sn["categoria"] == "Videos Clientes":
            m = re.search(r"https?://\S+", sn["contenido"])
            if m:
                urls.setdefault(m.group(0), []).append(sn["titulo"])
    for u, ts in urls.items():
        if len(ts) > 1:
            reporte.append(f"URL repetida en videos {ts}: revisa si es correcto")

    # Resumen
    print("\n=== RESUMEN ===")
    por_cat = {}
    for s in datos["snippets"]:
        por_cat[s["categoria"]] = por_cat.get(s["categoria"], 0) + 1
    for c, n in por_cat.items():
        print(f"  {c}: {n} snippets")
    por_tipo = {}
    for e in datos["enlaces"]:
        por_tipo[e["tipo"]] = por_tipo.get(e["tipo"], 0) + 1
    for t, n in por_tipo.items():
        print(f"  enlaces/{t}: {n}")
    print(f"  escalamientos: {len(datos['escalamientos'])}")
    print("\n=== NOTAS ===")
    for r in reporte:
        print("  -", r)

    Path("migracion_preview.json").write_text(
        json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nVista previa guardada en migracion_preview.json")

    if args.apply:
        print("\nCargando a Supabase...")
        cargar(datos)
        print("Listo.")
    else:
        print("\n(Modo vista previa: no se escribió nada. Usa --apply para cargar.)")


if __name__ == "__main__":
    main()
