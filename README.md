<p align="center">
  <img src="logo_t-hoarder.png" alt="t-hoarder-twscrape" width="90">
</p>

<h1 align="center">t-hoarder-twscrape</h1>

<p align="center">
  App de <a href="https://streamlit.io">Streamlit</a> para recoger, explorar y
  analizar datos de Twitter/X con <a href="https://github.com/vladkens/twscrape">twscrape</a>.
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: GPL-3.0" src="https://img.shields.io/badge/License-GPLv3-blue.svg"></a>
</p>

---

## Qué es

**t-hoarder-twscrape** es una interfaz gráfica para descargar tweets y perfiles de
Twitter/X mediante [twscrape](https://github.com/vladkens/twscrape) y trabajar con
esos datos sin salir de la app: organizarlos por proyectos, explorarlos en un
dashboard interactivo, generar gráficas de actividad y construir grafos de
retweets/menciones con detección de comunidades.

Es la evolución de la familia de herramientas **t-hoarder**, adaptada al scraping
con twscrape.

## Características

La app se organiza en secciones (barra superior):

✅ **Project** — crea y selecciona el proyecto de trabajo; cada proyecto agrupa sus datasets.  
✅ **Download** — descargas con twscrape: búsqueda histórica (*Search*), timeline de usuario (*User TL*), retweets y respuestas de un dataset.  
✅ **Dashboard** — dashboard interactivo (HTML autocontenido) para explorar un dataset: KPIs, ritmo de publicación, mapa de calor de métricas y tabla filtrable.  
✅ **Tools** — *Merge datasets* (unir y deduplicar) y *Clean dataset* (limpieza por idioma/criterios), con contexto append-only que conserva el historial.  
✅ **Graphs** — detección de comunidades, generación de grafos (GDF/GEXF), clasificación de tweets por comunidad y visor interactivo con ForceAtlas2 en el navegador.  
✅ **Charts** — gráficas de análisis para tweets y para perfiles de usuario.  
✅ **Settings** — gestión de cuentas de twscrape (alta, activas, borrado).

## Requisitos

- **Python 3.11+** (desarrollada sobre 3.13).
- Una o varias **cuentas de Twitter/X** para que twscrape pueda autenticarse.

## Instalación

Esta guía está pensada para que la pueda seguir cualquier persona, sin dar por
sabido el uso de la terminal. Son cuatro pasos: instalar Python, descargar la
app, instalar sus dependencias y arrancarla.

### Paso 1 · Instalar Python

La app funciona con **Python 3.11 o superior**.

1. Ve a [python.org/downloads](https://www.python.org/downloads/) y descarga el instalador para tu sistema.
2. Ejecuta el instalador.
3. **⚠️ Muy importante (Windows):** en la primera pantalla del instalador, marca la casilla **«Add python.exe to PATH»** antes de pulsar «Install Now». Si no la marcas, los comandos siguientes no funcionarán.
4. Termina la instalación.

Para comprobar que quedó bien instalado, abre una terminal (ver Paso 3) y escribe:

```bash
python --version
```

Debe responder algo como `Python 3.13.x`. (En macOS/Linux puede que tengas que
escribir `python3` en lugar de `python`.)

### Paso 2 · Descargar la app

Tienes dos maneras. Si no usas git, elige la **Opción A**.

**Opción A · Descargar el ZIP (la más sencilla, sin git)**

1. Abre la página del proyecto en GitHub.
2. Pulsa el botón verde **« Code »** y luego **« Download ZIP »**.
3. Descomprime el archivo `.zip` donde quieras tenerlo. Se creará una carpeta llamada algo como `t-hoarder-twscrape-main`.

> **⚠️ Importante — dónde colocar la carpeta:** elige una ruta cuyas carpetas
> **no contengan espacios, ni acentos, ni caracteres especiales** (`ñ`, `á`,
> `#`, `&`…). Rutas con esos caracteres dan problemas al ejecutar la app. Por
> ejemplo, evita `C:\Users\José Ramón\Escritorio\...` y usa algo como
> `C:\apps\t-hoarder-twscrape`.

**Opción B · Clonar con git** (si ya usas git)

```bash
git clone <URL-del-repo> t-hoarder-twscrape
```

### Paso 3 · Abrir una terminal dentro de la carpeta de la app

Necesitas abrir una terminal **situada en la carpeta** que acabas de descargar
(la que contiene las carpetas `app` y `scripts`).

- **Windows:** abre esa carpeta en el Explorador de archivos, haz clic en la barra de direcciones (arriba), escribe `powershell` y pulsa Enter. Se abrirá una terminal ya colocada en esa carpeta.
- **macOS:** abre la app **Terminal**, escribe `cd ` (con un espacio al final) y arrastra la carpeta sobre la ventana de Terminal; pulsa Enter.
- **Linux:** haz clic derecho dentro de la carpeta y elige «Abrir un terminal aquí» (o usa `cd` hasta la carpeta).

### Paso 4 · Instalar las dependencias

En la misma terminal del Paso 3, copia y pega este comando:

```bash
pip install -r app/requirements.txt
```

Esto descarga e instala las librerías que la app necesita (Streamlit, pandas,
matplotlib, twscrape…). Tarda un poco la primera vez; solo hay que hacerlo una
vez. Son librerías habituales, así que no interfieren con otros programas.

> Las stopwords de NLTK (usadas en las nubes de palabras) se descargan solas la
> primera vez que se generan esas gráficas.

## Ejecución

En la terminal (situada en la carpeta de la app, Paso 3), arranca la app:

```bash
streamlit run app/app.py
```

Se abrirá sola en tu navegador (si no, entra a `http://localhost:8501`). Para
**parar** la app, vuelve a la terminal y pulsa `Ctrl + C`.

Cada vez que quieras volver a usarla, repite solo este último paso: abre la
terminal en la carpeta de la app (Paso 3) y ejecuta `streamlit run app/app.py`.

> **Atajo en Windows:** el repositorio incluye `restart_app.ps1`, que cierra
> cualquier instancia previa y arranca la app. Haz clic derecho sobre él →
> «Ejecutar con PowerShell».

### Crear un acceso directo con icono (opcional)

Para no tener que abrir la terminal cada vez, puedes crear un acceso directo con
el icono de t-hoarder y arrancar la app con un doble clic.

**Windows**

1. Clic derecho en el Escritorio (o donde quieras) → **Nuevo → Acceso directo**.
2. En «Escribe la ubicación del elemento», pega lo siguiente, sustituyendo `RUTA` por la ruta real de tu carpeta:
   ```
   powershell.exe -ExecutionPolicy Bypass -File "RUTA\restart_app.ps1"
   ```
3. Ponle un nombre (por ejemplo `t-hoarder-twscrape`) y pulsa «Finalizar».
4. Clic derecho en el acceso directo → **Propiedades** → botón **«Cambiar icono…»** → **«Examinar…»** → selecciona el archivo **`t-hoarder.ico`** de la carpeta de la app → Aceptar.

**macOS**

1. En la carpeta de la app, crea un archivo de texto llamado `t-hoarder.command` con este contenido:
   ```bash
   #!/bin/bash
   cd "$(dirname "$0")"
   streamlit run app/app.py
   ```
2. Dale permiso de ejecución: abre Terminal en la carpeta y ejecuta
   `chmod +x t-hoarder.command`. Ya puedes arrancar la app con doble clic sobre él.
3. Para el icono: selecciona `t-hoarder.command`, pulsa **Cmd + I** (Obtener información), abre `logo_t-hoarder.png` en Vista Previa, cópialo (**Cmd + C**) y pégalo (**Cmd + V**) sobre el icono pequeño de arriba a la izquierda de la ventana de información.

**Linux**

1. En la carpeta de la app, crea un archivo `t-hoarder.desktop` con este contenido, sustituyendo `RUTA` por la ruta real de tu carpeta:
   ```ini
   [Desktop Entry]
   Type=Application
   Name=t-hoarder-twscrape
   Exec=bash -c "cd 'RUTA' && streamlit run app/app.py"
   Icon=RUTA/logo_t-hoarder.png
   Terminal=true
   ```
2. Márcalo como ejecutable (clic derecho → Propiedades → Permisos → «Permitir ejecutar como programa», o `chmod +x t-hoarder.desktop`). Según el escritorio, puede que la primera vez tengas que confirmar «Permitir lanzar».

## Configuración de cuentas

twscrape necesita al menos una cuenta **autenticada y con cookies** para poder
descargar datos. Si se dan de alta más cuentas, las irá rotando para repartir la
cuota de peticiones. Recomendaciones:

- Un **pool de 5 cuentas o más**.
- **No usar tu cuenta personal**, por si en algún momento hubiera un bloqueo por parte de Twitter/X.
- Es preferible que las cuentas tengan **cierta antigüedad y actividad**.

### ¿Cómo obtener las cookies de una cuenta?

1. Abre **Chrome** e inicia sesión en [https://x.com](https://x.com) con la cuenta que vayas a dar de alta.
2. Pulsa **F12** (Herramientas para desarrolladores) → pestaña **Application** → **Cookies** → `https://x.com`.
3. Copia los valores de **`auth_token`** y **`ct0`**.

### Dar de alta la cuenta

En **Settings → New Account**, cumplimenta:

- **Username** — nombre de usuario de la cuenta
- **Password** — contraseña de la cuenta
- **Email** — email asociado a la cuenta
- **Email Password** — contraseña de ese email
- **Auth Token** — cookie `auth_token` obtenida arriba
- **ct0** — cookie `ct0` obtenida arriba

## Estructura del repo

```
app/          App Streamlit (app.py, requirements.txt)
scripts/      Módulos de scraping y lógica (accounts, download, scraping,
              projects, context, graphs, charts, dashboard, utils…)
logo_t-hoarder.png / t-hoarder.ico   Marca de la app
```

Los datos recogidos (`data/`), las credenciales de twscrape (`accounts.db`) y las
notas internas de desarrollo no forman parte del repositorio.

## Agradecimientos

- [**vladkens**](https://github.com/vladkens) por su librería [twscrape](https://github.com/vladkens/twscrape).
- **Agustín Nieto** ([@agusnieto77](https://github.com/agusnieto77)) por su librería [twscraper](https://github.com/agusnieto77/twscraper), que me sirvió de base para el uso de twscrape.

## Licencia

Distribuido bajo la **GNU General Public License v3.0**. Ver [LICENSE](LICENSE).

Copyright (C) 2026 María Luz Congosto ([@congosto](https://github.com/congosto)).

> **Uso responsable:** esta herramienta hace scraping de Twitter/X, lo que puede
> ir en contra de los términos de servicio de la plataforma. Úsala de forma
> responsable, para investigación y análisis, y bajo tu propia responsabilidad.
