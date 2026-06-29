# t-hoarder_twscrape

App de Streamlit para explorar y analizar datos recogidos con twscrape (Twitter/X).

## Especificaciones funcionales

Las especificaciones de producto (lo que debe hacer la app) viven en `especificaciones/*.txt`, no en este archivo. Léelas antes de implementar o modificar funcionalidad:

- `especificaciones/gui.txt` — comportamiento y diseño de la interfaz (Streamlit).
- `especificaciones/metadatos.txt` — metadatos de tweets/usuarios.
- `especificaciones/metadatos_rt.txt` — metadatos específicos de retweets.
- `especificaciones/contents.txt` — especificación de contenidos.
- `especificaciones/grafos.txt` — especificación de grafos/redes.

Cada archivo tiene una copia `.bak` junto a él como histórico manual de la versión anterior (no hay control de versiones git en este directorio).

## Estructura del repo

- `app/` — app Streamlit en producción (`app.py`, `requirements.txt`, `data/`).
- `scripts/` — módulos Python de scraping/lógica (accounts, context, download, projects, scraping, utils, graphs, charts, nb_charts, nb_charts_profile, utils_charts), importados por `app/app.py` añadiendo `scripts/` a `sys.path`.
- `data/` — datos recogidos (csv, cachés).

## Notas de trabajo

- Cuando el usuario aporte una especificación nueva o actualizada de GUI/metadatos en el chat, guárdala en el archivo `.txt` correspondiente dentro de `especificaciones/`, moviendo la versión anterior a `.bak`.
