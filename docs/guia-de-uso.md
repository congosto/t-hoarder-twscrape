<p align="center">
  <img src="../logo_t-hoarder.png" alt="t-hoarder-twscrape" width="90">
</p>

<h1 align="center">Guía de uso</h1>

<p align="center">
  <b>Español</b> · <a href="user-guide.en.md">English</a>
</p>

---

**Índice** ·
[Estructura](#estructura-de-t-hoarder-twscrape) ·
[Project](#project) ·
[Download](#download) ·
[Dashboard](#dashboard) ·
[Tools](#tools) ·
[Graphs](#graphs) ·
[Charts](#charts) ·
[Settings](#settings)

## Estructura de t-hoarder-twscrape

La pantalla de la app se organiza en cinco zonas fijas, iguales en todas las
secciones. Una vez entendida esta estructura, todas las funciones se manejan de
la misma manera: se elige la función arriba, se rellena el formulario a la
izquierda, se lanza la operación y el resultado aparece en el centro.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  logo · t-hoarder-twscrape                                                   │
│  [Project] [Download] [Dashboard] [Tools] [Graphs] [Charts] [Settings] [Help]│
├────────────────┬────────────────────────────────────────────┬────────────────┤
│  Sub-funciones │                                            │  Contexto de   │
│  Formulario    │                 Resultados                 │  ejecución     │
│  de datos      │                                            │                │
│  [Ejecutar]    │                                            │                │
├────────────────┴────────────────────────────────────────────┴────────────────┤
│  Consola de ejecución                                                        │
└──────────────────────────────────────────────────────────────────────────────┘
```

![La app con sus cinco zonas: menú superior, formulario a la izquierda, resultados en el centro (un dashboard), contexto a la derecha y consola abajo](img/app_overview.png)

### Parte superior · Menú de funciones

Una fila de botones da acceso a las funciones de la app:

- **Project** — crear y seleccionar el proyecto de trabajo.
- **Download** — descargas de datos con twscrape.
- **Dashboard** — dashboard interactivo de un dataset.
- **Tools** — utilidades sobre datasets (unir, limpiar, comparar…).
- **Graphs** — grafos de relaciones y detección de comunidades.
- **Charts** — gráficas de análisis de tweets y de perfiles.
- **Settings** — gestión de las cuentas de twscrape.
- **Help** — esta guía de uso, mostrada dentro de la propia app.

Al arrancar, la sección seleccionada es **Project**: lo primero es siempre
elegir (o crear) el proyecto sobre el que se va a trabajar.

### Parte izquierda · Sub-funciones y formulario

Cada función se divide en **sub-funciones** (por ejemplo, Download ofrece
Search, User TL, Retweets, Comments y Advanced Comments). Al elegir una
sub-función, esta zona muestra su **formulario de entrada de datos** y, al
final, el **botón que lanza la operación**.

### Parte central · Resultados

Aquí aparece el resultado de la operación ejecutada: una tabla con los datos
generados, las gráficas de Charts (en modo carrusel, una cada vez), el
dashboard o los informes HTML embebidos, o el visor interactivo de grafos.
Cuando el resultado es un fichero, se muestra una vista previa y, si procede,
un botón para descargarlo. El botón **«Borrar resultados»** limpia el panel.

### Parte derecha · Contexto de ejecución

Resume la situación de trabajo actual:

- Las **cuentas activas** de twscrape.
- El **proyecto activo**.
- Las **descargas con contexto guardado** del proyecto: una entrada por
  dataset, expandible para ver el detalle de su descarga (query o usuarios,
  fechas, producto, frecuencia).

### Parte inferior · Consola de ejecución

Muestra el progreso de la operación en curso, un mensaje por línea, según se
va ejecutando. Los errores se resaltan en rojo. En las operaciones largas
(descargas), es la forma de seguir por dónde va el proceso.

## Project

Para organizar los datos, la app propone el concepto de **proyecto**: un
proyecto agrupa un conjunto de datasets relacionados (por ejemplo, todas las
descargas sobre un mismo tema o evento). En disco, cada proyecto es
simplemente una carpeta dentro de `data/` con su nombre, y todos los ficheros
de sus datasets viven ahí.

El número de datasets por proyecto no está limitado, aunque si hay demasiados
puede resultar incómodo trabajar con ellos. Queda al criterio de cada uno la
forma de organizarse.

**Lo primero, siempre**: la app arranca en esta sección porque, antes de
descargar o analizar nada, hay que tener un proyecto activo — crear uno nuevo
o seleccionar uno existente.

- **Select project** — selecciona el proyecto de trabajo en un desplegable
  con los proyectos activos, ordenados por actividad (el que tuvo movimiento
  más recientemente, primero). Al seleccionarlo, en la ventana de Contexto
  (parte derecha) aparecen, además del número de cuentas activas, el proyecto
  activo y sus datasets con su contexto (cada uno expandible para ver el
  detalle de sus descargas). A partir de ese momento se trabaja **solo con
  los datos de ese proyecto**: los desplegables de Dataset del resto de
  secciones listan únicamente sus datasets.

- **New project** — crea un proyecto nuevo, lo que equivale a crear la
  carpeta `data/{nombre}`. El proyecto recién creado queda además **activado
  como proyecto de trabajo**, así que se puede ir directamente a Download a
  llenarlo de datos. El nombre no puede estar vacío ni contener caracteres no
  válidos para una carpeta (`\ / : * ? " < > |`); si ya existe un proyecto
  con ese nombre (activo o desactivado), la consola avisa del error.

- **Active projects** — muestra en el panel de resultados la lista de los
  proyectos existentes (los activos).

- **Deactivate project** — permite **archivar** un proyecto que no se está
  usando con frecuencia, para que la lista de proyectos activos no crezca
  demasiado. **Nunca borra nada**: solo mueve la carpeta del proyecto de
  `data/{proyecto}` a `data/desactivated/{proyecto}`, con todos sus datos
  intactos. Si el proyecto archivado era el activo, deja de estarlo (habrá
  que seleccionar otro o reactivarlo).

- **Reactivate project** — el camino de vuelta: pasa un proyecto desactivado
  al grupo de proyectos activos (mueve su carpeta de `data/desactivated/` de
  nuevo a `data/`) y lo deja **seleccionado como proyecto de trabajo**.

## Download

Esta sección descarga datos de Twitter/X mediante twscrape. Antes de entrar
en las opciones conviene entender cuatro conceptos que explican por qué las
descargas funcionan como funcionan.

### Conceptos previos

- **Rate limit** — X limita las peticiones que acepta de cada cuenta, por
  operación y en ciclos de **15 minutos**. En la búsqueda, la cuota ronda las
  50 peticiones por ciclo y cada petición trae una página de ~20 tweets: unos
  **900–1.000 tweets por cuenta cada 15 minutos**. No es una cifra fija ni
  documentada: X la anuncia en cada respuesta y puede cambiarla; twscrape
  simplemente la obedece. Por eso la app pide como máximo ~900 tweets por
  consulta y hace una pausa de unos segundos entre consultas: quemar la cuota
  en ráfaga solo consigue que X devuelva respuestas vacías.

- **Pool de cuentas** — cuando una cuenta agota su cuota para una operación,
  twscrape la deja en reserva hasta que X la desbloquea y **continúa con otra
  cuenta activa** del pool, de forma transparente. Cuantas más cuentas dadas
  de alta (ver *Settings*), más caudal de descarga; con un pool de 5 o más se
  trabaja con comodidad.

- **Por qué las descargas van delimitadas entre fechas** — el buscador de X
  no devuelve todo lo que existe de una consulta: cada búsqueda tiene una
  profundidad limitada. Para no perder tweets, la app trocea el periodo
  pedido en **ventanas de tiempo** (la *frequency*: mes, semana, día, horas…)
  y lanza una consulta por ventana. Si aun así una ventana devuelve tantos
  tweets que roza el techo del buscador (500 o más), ese tramo puede estar
  incompleto: es lo que llamamos **overflow**, y la app lo detecta y lo
  gestiona (cómo, depende del modo de descarga; ver *Search*).

- **Product: Top y Latest** — X ofrece dos productos de búsqueda, los mismos
  que las pestañas de su buscador web:
  - **Top** (destacados): una selección curada de los tweets más relevantes.
  - **Latest** (recientes): el flujo cronológico.

  De forma empírica hemos detectado que **Latest funciona mejor en
  frecuencias de un día o mayores, y Top en las menores de un día** — y
  también que **el índice denso de Top solo cubre los últimos 7 días
  naturales (UTC)**: el día D-7 aún se recupera completo, pero el D-8
  desaparece de golpe (las ventanas de menos de un día pasan a devolver ~0).
  De los días más antiguos Top solo conserva un **residuo de lo más viral**,
  consultable con ventanas de un día o más; Latest no tiene ese acantilado,
  aunque en datos viejos también devuelve bastante menos que en fresco. Por
  eso la app proporciona un **método optimizado** que usa la mejor opción en
  cada momento:

  1. Según la longitud del periodo pedido, elige la frecuencia inicial
     (hasta 1 mes → ventanas de 1 día; hasta 6 meses → de 1 semana; más → de
     1 mes), siempre con *Latest*.
  2. Si una ventana desborda (500 tweets o más: puede estar incompleta), la
     **re-descarga subdividida** en la siguiente frecuencia de la escalera
     mes → semana → día → 6 h → 3 h → 1 h → 30 min, recursivamente hasta que
     ninguna subventana desborde o se llegue a los 30 minutos.
  3. Al bajar de un día, cambia de *Latest* a *Top* — pero **solo dentro de
     la memoria de Top** (los últimos 7 días): en las ventanas intradía más
     antiguas mantiene *Latest*, que ahí es la única opción que devuelve
     datos.
  4. En las ventanas de un día o más anteriores a esa memoria lanza además
     una **petición extra con Top** para rescatar el residuo viral que
     Latest ya no devuelve entero (los duplicados se eliminan al rematar la
     descarga).

  El método respeta la pausa entre todas las consultas, también las de las
  subdivisiones, para no quemar la cuota en ráfaga.

### Dos tipos de descargas

- Las **principales** — *Search* y *User TL*. Son las que crean un dataset:
  descargan tweets delimitados entre dos fechas, a partir de una query o de
  una lista de usuarios.
- Las **complementarias** — *Retweets*, *Comments* y *Advanced Comments*.
  Parten de un dataset ya descargado y lo enriquecen: quién retuiteó sus
  tweets y qué respuestas recibieron. Son la materia prima de los grafos de
  la sección *Graphs*.

Todas las descargas son **reanudables**: si se interrumpen (o se cortan a
propósito), basta relanzarlas con el mismo dataset y continúan donde se
quedaron, gracias al contexto que se guarda con cada dataset.

### Las opciones, una a una

- **Search** — búsqueda histórica de tweets a partir de una query. Campos:
  - *Dataset*: uno existente (para continuar o ampliar una descarga) o
    «➕ nuevo dataset…» para crear uno.
  - *Load context*: si el dataset ya tiene descargas, rellena el formulario
    con los parámetros guardados de la última.
  - *Query*: la consulta, con la misma sintaxis que el buscador de X
    (admite operadores avanzados: `"frase exacta"`, `OR`, `from:usuario`,
    `lang:es`, `filter:replies`…).
  - *From / To*: el periodo, en formato `YYYY-mm-dd HH:MM:SS`.
  - *Mode*: la decisión clave del formulario.
    - **Optimized** (recomendado): no pide nada más. Aplica el **método
      optimizado** descrito en los conceptos previos: la app elige sola el
      product y la frecuencia y subdivide las ventanas que desbordan hasta
      capturar cada tramo completo.
    - **Manual**: pide además *Product* (Top | Latest) y *Frequency*, y los
      usa tal cual. El overflow aquí solo se avisa en consola y se anota en
      `{dataset}_overflow.csv`; con ese fichero, el usuario decide
      re-descargar los tramos incompletos con una frecuencia más fina (a un
      dataset nuevo) y unirlos después con *Tools → Merge datasets*. Si se
      pide *Top* sobre un rango que rebasa su memoria de 7 días, la app lo
      respeta pero lo avisa en consola.
  - Ficheros que genera: `{dataset}.csv` (los tweets del periodo, sin
    duplicados), `{dataset}_raw.csv` (todo lo recolectado, sin recortar), el
    log de contexto y, si lo hubo, el log de overflow.

- **User TL** — descarga los tweets de uno o varios usuarios (lista
  separada por comas, sin `@`). El resto del formulario es como el de
  Search: fechas, *Load context* y los mismos dos modos; en Optimized, el
  criterio se aplica **usuario a usuario**. En lugar de pedir el timeline
  del usuario (que X limita a los ~3.200 tweets más recientes), se hace una
  búsqueda `from:usuario`, lo que permite descargar **todos sus tweets
  originales** sin ese límite. La contrapartida es que **no se descargan los
  retweets que hizo el usuario** (la búsqueda no los devuelve).

- **Retweets** — para cada tweet del dataset con al menos *Min RTs*
  retweets, descarga **los perfiles de los usuarios que lo retuitearon** (no
  los retweets como tweets): username, seguidores, fecha de creación de la
  cuenta, localización declarada… Genera `{dataset}_RTs.csv`, con una fila
  por retuiteador y tweet. El umbral *Min RTs* sirve para centrarse en los
  tweets con difusión y no gastar cuota en los que apenas se retuitearon.
  Es la base de los grafos de RTs de *Graphs*.

- **Comments** — para cada tweet del dataset con al menos *Min Replies*
  respuestas, descarga esas respuestas (que son tweets completos) y genera
  `{dataset}_replies.csv`. Usa el hilo de conversación de cada tweet, que es
  rápido pero no siempre llega a todas las respuestas de las conversaciones
  grandes.

- **Advanced Comments** — el mismo objetivo que Comments, pero usando el
  buscador: para cada tweet lanza búsquedas de su conversación
  (`conversation_id`) troceadas por ventanas desde la fecha del tweet hasta
  *Last* días después, con la *Frequency* elegida. Llega mucho más hondo en
  conversaciones con cientos de respuestas, a cambio de gastar más cuota.
  Tiene su propia detección de overflow
  (`{dataset}_replies_advanced_overflow.csv`) y genera
  `{dataset}_replies_advanced.csv`.

## Dashboard

El dashboard se documenta solo: dado un dataset, genera una vista interactiva
con los **principales KPIs** (tweets, visualizaciones, retweets, respuestas,
citas, y el día y hora de máxima actividad), una **gráfica de actividad**
(el ritmo de publicación a lo largo del periodo) y los **tweets más
relevantes**, ordenables por distintos criterios (visualizaciones, retweets,
respuestas, likes, seguidores del autor, fecha…).

Toda la vista se puede **filtrar** — por rango de fechas, tipo de tweet
(original, respuesta, cita), idioma o **palabras del texto** — y los KPIs,
la gráfica y la tabla se recalculan al instante. La selección filtrada puede
exportarse a CSV.

Manejo: se elige el *Dataset* (y un título opcional), se pulsa **Show
dashboard** y el resultado aparece en el panel central. El dashboard es un
**HTML autocontenido** (`{dataset}_dashboard.html` en la carpeta del
proyecto) que funciona sin conexión y sin instalar nada: con el botón de
descarga se puede guardar y **compartir como un único archivo**, que
cualquiera puede abrir en su navegador. Si el dataset no ha cambiado desde
la última vez, se reutiliza el ya generado en vez de recalcularlo.

## Tools

Herramientas para manejar los datasets del proyecto activo. Dos de ellas
(Merge y Clean) sobrescriben datasets, así que conviene saber desde ya la
regla de la casa: **t-hoarder-twscrape nunca borra ningún dato**. Cuando el
resultado de una operación se deja en un dataset que ya existía, la versión
anterior se guarda antes con un sufijo con la fecha de la operación
(`{dataset}_prev_<fecha>.csv`), y siempre se puede volver a ella.

- **Merge datasets** — une datasets **del mismo tipo** (todos de búsqueda o
  todos de timeline) que estén en el proyecto activo, eliminando los tweets
  duplicados. Su uso típico: completar una descarga manual en la que hubo
  overflow — se re-descargan los tramos incompletos con una frecuencia más
  fina en un dataset aparte y se unen aquí con el original. Si el dataset
  destino es uno de los de origen, su versión anterior queda guardada con el
  sufijo de fecha.

- **Clean dataset** — hay que ser conscientes de que el buscador de X
  devuelve un pequeño porcentaje de tweets que no se corresponden con la
  query pedida. Esta utilidad filtra el dataset por tres criterios
  combinables: **idiomas** (los que se conservan), **palabras positivas** (el
  tweet se mantiene si contiene alguna) y **falsas positivas** (se descartan
  los tweets que las contengan); las comparaciones ignoran mayúsculas y
  acentos. Como resultado proporciona el dataset filtrado y muestra además
  **los tweets eliminados**, ordenados por retweets, para poder comprobar de
  un vistazo que el filtro fue correcto y no se llevó por delante tweets
  válidos. Igual que en Merge, si el destino ya existía, la versión anterior
  queda guardada con el sufijo de fecha.

- **Restore dataset** — el arrepentimiento tiene arreglo: si un filtro (o un
  merge) no convence, esta opción devuelve el dataset a una versión
  anterior, elegida por la fecha de su sufijo en un desplegable (que muestra
  fecha y tamaño de cada una). La restauración también guarda antes la
  versión actual, así que es reversible en ambos sentidos.

- **Compare datasets** — muestra las diferencias entre dos o más datasets.
  Es útil, por ejemplo, para comparar descargas de la misma query hechas con
  distintas frecuencias o productos. Genera un informe HTML autocontenido
  con tres bloques: el resumen de cada dataset (periodo, número de tweets y
  suma de sus impactos: views, RTs, respuestas, citas), los **tweets
  compartidos** entre todos ellos (en número y porcentaje), y una **gráfica
  temporal** con los tweets recogidos por cada descarga, con la unidad de
  tiempo ajustable (hora, día, semana, mes).

- **Location** — analiza la localización declarada en el perfil de los
  autores del dataset y la estructura en **país, región y ciudad** (para
  España, la región es la comunidad autónoma). La geocodificación es offline
  (no consume cuota) y genera `{dataset}_loc.csv`. Es útil, sobre todo, para
  añadir la localización como atributo de los nodos en los grafos de
  *Graphs*.

## Graphs

Esta sección construye y visualiza **grafos de relaciones entre usuarios**:
quién retuitea o responde a quién. Son la herramienta clásica para ver la
estructura de una conversación — los polos que se forman, quiénes son los
usuarios centrales de cada uno y cómo se conectan (o no) entre sí.

### Conceptos previos

- **La relación** — el grafo se construye a partir de una de las descargas
  complementarias de *Download*: **RT** (quién retuiteó a quién, del fichero
  de Retweets), **replies** o **replies_advanced** (quién respondió a quién,
  de Comments o Advanced Comments). Cada usuario es un nodo; cada relación,
  una arista dirigida cuyo peso es el número de veces que se repite.

- **Las comunidades** — grupos de usuarios más conectados entre sí que con
  el resto, detectados con el algoritmo de **Louvain**. En un grafo de RTs
  suelen corresponder a los polos de opinión de la conversación. El
  algoritmo no es determinista (cada ejecución puede dar comunidades algo
  distintas), por eso el resultado se guarda en disco y los pasos siguientes
  reutilizan siempre el mismo en vez de recalcularlo.

- **La relevancia de un usuario** se mide por su **weighted indegree**: el
  número de RTs (o respuestas) que recibió. Es lo que determina el tamaño de
  cada nodo en el visor.

El flujo típico es: **Detect communities** → **Generate graph** →
**Visualize graph** (y, si se quieren analizar los tweets por comunidad en
*Charts*, también **Classify tweets**).

### Las opciones, una a una

- **Detect communities** — se necesitan las **relaciones** (RTs, replies o
  replies_advanced), así que es imprescindible haberlas descargado
  previamente en *Download*. Dado un dataset y una relación, construye el
  grafo, se queda con su **componente gigante** (la parte conexa más grande)
  y detecta las comunidades con el algoritmo de **Louvain**. Como resultado
  proporciona la tabla de comunidades con su tamaño en porcentaje de nodos
  (`{dataset}_{relation}_communities.csv`) y la asignación de cada usuario a
  su comunidad, con sus grados de entrada y salida
  (`{dataset}_users_{relation}_communities.csv`).

- **Generate graph** — dado un dataset y una relación, genera el grafo en
  formato **GDF o GEXF**, listo para el visor de la app o para abrirlo en
  [Gephi](https://gephi.org). Cada nodo lleva como atributos el perfil de su
  usuario: antigüedad de la cuenta (año de creación), verificación, y sus
  métricas — seguidores, seguidos, tweets, favoritos y listas — en escala
  logarítmica. Dos casillas permiten añadir además la **comunidad** (de
  Detect communities) y la **localización** (de Tools → Location), muy
  útiles para colorear o filtrar el grafo.

- **Classify tweets** — requiere haber ejecutado previamente *Detect
  communities*. Dado un dataset y una relación, clasifica cada tweet con la
  comunidad de su autor y genera `{dataset}_{relation}_classified.csv`. Es
  el fichero que usa *Charts* para las gráficas por comunidad (qué dice
  cada polo de la conversación).

- **Visualize graph** — renderiza un grafo del proyecto (.gdf/.gexf) con el
  layout **ForceAtlas2** (el mismo de Gephi), calculado en vivo en el
  navegador: el grafo se ve desplegarse, y se puede pausar y relanzar. En el
  formulario se especifican el **máximo de etiquetas por comunidad** y el
  **número de iteraciones**; ya en el visor se pueden ajustar los parámetros
  del layout (*Scaling*, *Gravity*, *LinLog*, *Dissuade hubs*). Cada
  comunidad tiene un color (las menores del 2% se agrupan en gris como
  «Otros») y el tamaño de cada nodo refleja su weighted indegree. Qué se
  puede hacer:
  - **Explorar**: zoom y desplazamiento; al pasar el ratón por un nodo se
    resalta su vecindario y un tooltip muestra sus atributos; el clic abre
    un panel con sus métricas y el enlace a su perfil en x.com; hay un
    buscador de nodos con zoom al usuario encontrado.
  - **Filtrar**: la leyenda de comunidades es clicable para ocultar o
    mostrar cada una, y un filtro por grado (indegree mínimo) permite
    quedarse con los usuarios relevantes.
  - **Medir**: la barra de estado muestra densidad, reciprocidad y
    modularidad del grafo.
  - **Exportar**: a **PNG** en alta resolución (respetando los filtros
    activos, con la leyenda incluida) o a **GEXF** con posiciones y colores,
    para seguir trabajando en Gephi.

## Charts

Gráficas de análisis en profundidad, listas para usar en un informe o una
publicación. Se generan dos conjuntos, uno por cada tipo de dataset:

- **Tweets** — para los datasets de *Search*: tweets relacionados con una
  búsqueda de palabras clave o hashtags, donde interactúan perfiles muy
  diversos. Las gráficas miran la conversación en conjunto: actividad e
  impacto (alcance, RTs), los **influencers** que la mueven, palabras más
  frecuentes, menciones a medios…

  Se especifica el *Dataset*, el prefijo del título que llevarán todas las
  gráficas, la zona horaria y los valores mínimos de alcance y de RTs a
  partir de los cuales se etiqueta a los influencers en las gráficas.
  Opcionalmente se puede:
  - **Incluir las comunidades** (hay que haberlas calculado antes en
    *Graphs*, con *Detect communities* y *Classify tweets*): añade las
    gráficas por comunidad — cuánto publica y qué palabras usa cada polo de
    la conversación.
  - **Añadir un fichero de topics**, para seguir la presencia de esos temas
    en los tweets.
  - **Añadir un fichero de events**, para anotar las gráficas en posiciones
    específicas del tiempo (el «qué pasó ese día» que explica un pico).
  - **Hacer zoom**: restringir todas las gráficas al tramo entre dos fechas
    dadas, en vez de usar todo el periodo.

- **Users** — para los datasets de *User TL*: los tweets de uno o más
  perfiles. Las gráficas se generan **para un solo perfil cada vez**, así
  que además del *Dataset* hay que indicar el usuario, junto al prefijo del
  título y la zona horaria. Retratan el comportamiento de la cuenta: su
  **rutina diaria** (a qué horas publica, y desde qué aplicación), su ritmo
  semanal y mensual, el impacto y engagement de sus tweets, la evolución por
  idioma y por fuente, y sus palabras más frecuentes. También admite los
  ficheros de topics y de events.

En ambos casos hay dos botones: **generar las gráficas**, que se muestran en
el panel de resultados en modo carrusel y se guardan como PNG en
`data/{proyecto}/{dataset}_graficas/`, o **generar un informe HTML
autocontenido** con todas ellas (imágenes embebidas, cabecera e índice): un
único archivo que se puede compartir y abrir en cualquier navegador.

## Settings

Gestión de las cuentas de twscrape. Es lo primero que hay que configurar
tras instalar la app — y, una vez configurado, lo que menos se toca (por eso
el botón va al final del menú).

twscrape necesita al menos una cuenta **autenticada y con cookies** para
poder descargar datos. Si se dan de alta más cuentas, las irá rotando para
repartir la cuota de peticiones (el *pool de cuentas* explicado en
*Download*). Recomendaciones:

- Un **pool de 5 cuentas o más**.
- **No usar tu cuenta personal**, por si en algún momento hubiera un bloqueo
  por parte de Twitter/X.
- Es preferible que las cuentas tengan **cierta antigüedad y actividad**.

### ¿Cómo obtener las cookies de una cuenta?

1. Abre **Chrome** e inicia sesión en [https://x.com](https://x.com) con la
   cuenta que vayas a dar de alta.
2. Pulsa **F12** (Herramientas para desarrolladores) → pestaña
   **Application** → **Cookies** → `https://x.com`.
3. Copia los valores de **`auth_token`** y **`ct0`**.

### Las opciones

- **New Account** — da de alta una cuenta. Se cumplimenta:
  - *Username* — nombre de usuario de la cuenta
  - *Password* — contraseña de la cuenta
  - *Email* — email asociado a la cuenta
  - *Email Password* — contraseña de ese email
  - *Auth Token* — cookie `auth_token` obtenida arriba
  - *ct0* — cookie `ct0` obtenida arriba

- **Active Accounts** — muestra la lista de cuentas dadas de alta y su
  estado, para comprobar de un vistazo con cuántas se está descargando.

- **Delete Account** — elimina una cuenta del pool (por ejemplo, si X la ha
  bloqueado y ya no aporta cuota).
