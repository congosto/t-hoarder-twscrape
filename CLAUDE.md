# t-hoarder_twscrape

App de Streamlit para explorar y analizar datos recogidos con twscrape (Twitter/X).

## Especificaciones funcionales

Las especificaciones de producto (lo que debe hacer la app) viven en `especificaciones/*.txt`, no en este archivo. Son **notas internas locales** (autora + Claude): la carpeta está en `.gitignore` y no forma parte del repo público, que es solo código. Léelas antes de implementar o modificar funcionalidad:

- `especificaciones/gui.txt` — comportamiento y diseño de la interfaz (Streamlit).
- `especificaciones/metadatos.txt` — metadatos de tweets/usuarios.
- `especificaciones/metadatos_rt.txt` — metadatos específicos de retweets.
- `especificaciones/grafos.txt` — especificación de grafos/redes.

(No existe `contents.txt`: esa funcionalidad se implementó y se desechó deliberadamente, ver nota en `gui.txt`.)

Como `especificaciones/` no se commitea, los `.bak` que quedan junto a algunos `.txt` siguen siendo el histórico local de esos archivos (git no los cubre al estar ignorados).

## Estructura del repo

- `app/` — app Streamlit en producción (`app.py`, `requirements.txt`, `data/`).
- `scripts/` — módulos Python de scraping/lógica (accounts, context, download, projects, scraping, utils, graphs, charts, charts_tweets, charts_profile, utils_charts), importados por `app/app.py` añadiendo `scripts/` a `sys.path`.
- `data/` — datos recogidos (csv, cachés).

## Notas de trabajo

- Cuando el usuario aporte una especificación nueva o actualizada de GUI/metadatos en el chat, guárdala en el archivo `.txt` correspondiente dentro de `especificaciones/`. Esa carpeta es local e ignorada por git, así que **no** se commitea (a diferencia de los cambios de código, que sí).
