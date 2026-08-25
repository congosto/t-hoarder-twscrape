# -*- coding: utf-8 -*-
"""Traduccion de los topics al idioma del corpus.

Los topics se escriben en el idioma de quien analiza (español) y los tweets
estan en el suyo. Traducir los tweets no es viable —cientos de miles por
dataset—, pero los topics son diez terminos: se traducen una vez al idioma
mayoritario del dataset, se busca por todas las variantes y la grafica se
sigue etiquetando en español.

Las traducciones se cachean en {prefix}_topics_aliases.csv, al lado del
dataset: se traduce una sola vez y el fichero queda a la vista para corregir a
mano lo que el traductor no acierte (los topónimos y los nombres propios son
justo lo que peor lleva). Solo se cachean los aciertos, asi que un fallo de red
se reintenta en la siguiente ejecucion.

Dependencias: deep-translator, opcional. Sin ella los topics se buscan tal
como estan escritos, que es el comportamiento de toda la vida.
"""
import pandas as pd

ALIASES_SUFFIX = "_topics_aliases.csv"
WORDS_SUFFIX = "_word_translations.csv"

# Palabras por peticion al traducir la nube. Van unidas por saltos de linea y
# el motor las devuelve una por linea; si la cuenta no cuadra se reintenta el
# grupo palabra a palabra. Veinte es un equilibrio entre numero de peticiones y
# riesgo de que un grupo entero salga mal
_CHUNK = 20

# Codigos que Twitter/X usa para "esto no es texto en ningun idioma": tweets de
# solo imagen, emojis o enlaces. Si no se descartan, un dataset con muchos
# videos puede acabar declarando 'zxx' como idioma mayoritario
_NOT_A_LANG = {"und", "zxx", "mul", "art", "qam", "qct", "qht", "qme", "qst"}


def dominant_langs(df, min_share=0.10, max_langs=3):
    """Idiomas reales del dataset, de mas a menos frecuente, quedandose con los
    que pesan al menos min_share. Se admite mas de uno porque hay corpus
    genuinamente mixtos (un hashtag magrebi mezcla arabe y frances)."""
    if "lang" not in df.columns or df.empty:
        return []
    langs = df["lang"].dropna().astype(str).str.lower().str.split("-").str[0]
    langs = langs[~langs.isin(_NOT_A_LANG) & (langs != "")]
    if langs.empty:
        return []
    share = langs.value_counts(normalize=True)
    return list(share[share >= min_share].head(max_langs).index)


def _backends(source, target):
    """[(nombre, motor)] en orden de preferencia.

    Google es el que mejor lleva los toponimos, pero es un endpoint web sin
    contrato: estrangula por IP sin avisar y a partir de ahi responde "no
    translation was found" a absolutamente todo, incluidas palabras que
    tradujo bien cinco minutos antes. MyMemory es una API publica de verdad
    (1000 palabras al dia sin registrarse) y aguanta cuando el otro cierra el
    grifo; con diez topics por dataset y cache en disco, esa cuota sobra."""
    backends = []
    try:
        from deep_translator import GoogleTranslator
        backends.append(("Google", GoogleTranslator(source=source, target=target)))
    except Exception:
        pass
    try:
        from deep_translator import MyMemoryTranslator
        from deep_translator.constants import MY_MEMORY_LANGUAGES_TO_CODES
        # MyMemory quiere el nombre del idioma, no el codigo ISO, y su tabla va
        # por locales ("arabic" -> "ar-SA"): se invierte por el prefijo
        names = {}
        for name, code in MY_MEMORY_LANGUAGES_TO_CODES.items():
            names.setdefault(str(code).split("-")[0], name)
        if names.get(source) and names.get(target):
            backends.append(("MyMemory", MyMemoryTranslator(
                source=names[source], target=names[target])))
    except Exception:
        pass
    return backends


def translate_terms(terms, source, target, log=print):
    """{termino: traduccion}. Los terminos que ningun motor sepa traducir se
    quedan fuera: se seguiran buscando tal como esten escritos, que encuentra
    menos pero nunca es peor que no buscar nada."""
    terms = [str(t).strip() for t in terms if str(t).strip()]
    if not terms:
        return {}
    try:
        import deep_translator  # noqa: F401
    except ImportError:
        log("deep-translator not installed: topics are searched as written "
            "(pip install deep-translator to translate them)")
        return {}

    out, pending = {}, list(terms)
    for name, engine in _backends(source, target):
        failed, last_error = [], None
        for term in pending:
            # de uno en uno y no con translate_batch: el lote aborta entero al
            # primer termino que el motor no reconoce, y basta una errata en el
            # fichero de topics para quedarse sin ninguna traduccion
            try:
                result = (engine.translate(term) or "").strip()
            except Exception as exc:
                failed.append(term)
                last_error = exc
                continue
            if result and result.lower() != term.lower():
                out[term] = result
        pending = failed
        if not pending:
            break
        log(f"{name} could not translate {len(pending)} topics ({last_error}); "
            "trying the next engine")
    for term in pending:
        log(f"No translation of '{term}' to '{target}': it will be searched as written")
    return out


def _read_cache(path):
    if not path.exists():
        return pd.DataFrame(columns=["topic", "lang", "alias"])
    cache = pd.read_csv(path, dtype=str).fillna("")
    for col in ("topic", "lang", "alias"):
        if col not in cache.columns:
            cache[col] = ""
    return cache[["topic", "lang", "alias"]]


def resolve_topic_aliases(topics, tweets, project_dir, prefix, source="es", log=print):
    """Devuelve los topics con la columna aliases rellena con su traduccion al
    idioma (o idiomas) mayoritario del dataset.

    Un topic que ya trae aliases escritos a mano no se traduce: si alguien se
    ha molestado en poner el termino exacto, una traduccion automatica encima
    solo puede añadir falsos positivos."""
    topics = topics.copy()
    if "aliases" not in topics.columns:
        topics["aliases"] = ""
    topics["aliases"] = topics["aliases"].fillna("").astype(str)

    targets = [lang for lang in dominant_langs(tweets) if lang != source]
    if not targets:
        return topics

    cache_path = project_dir / f"{prefix}{ALIASES_SUFFIX}"
    cache = _read_cache(cache_path)
    known = {(row.topic, row.lang): row.alias for row in cache.itertuples()}

    pending = [str(t) for t, a in zip(topics["topics"], topics["aliases"]) if not a.strip()]
    new_rows = []
    for lang in targets:
        missing = [t for t in pending if (t, lang) not in known]
        if missing:
            log(f"Translating {len(missing)} topics {source} -> {lang}")
            for term, alias in translate_terms(missing, source, lang, log=log).items():
                known[(term, lang)] = alias
                new_rows.append({"topic": term, "lang": lang, "alias": alias})
    if new_rows:
        pd.concat([cache, pd.DataFrame(new_rows)], ignore_index=True).to_csv(
            cache_path, index=False)
        log(f"Topic translations saved to {cache_path.name}")

    aliases = []
    for topic, manual in zip(topics["topics"], topics["aliases"]):
        if manual.strip():
            aliases.append(manual)
            continue
        found = [known.get((str(topic), lang), "") for lang in targets]
        aliases.append("|".join(a for a in found if a))
    topics["aliases"] = aliases
    return topics


def _translate_chunked(words, source, target, log=print):
    """{palabra: traduccion} para una lista larga. Una peticion por palabra
    seria un centenar de viajes por nube; unidas por saltos de linea el motor
    las devuelve en bloque y bastan cinco."""
    out, pending = {}, list(words)
    for name, engine in _backends(source, target):
        failed = []
        for start in range(0, len(pending), _CHUNK):
            chunk = pending[start:start + _CHUNK]
            try:
                answer = engine.translate("\n".join(chunk)) or ""
                parts = [p.strip() for p in answer.split("\n") if p.strip()]
            except Exception as exc:
                log(f"{name} failed on a block of {len(chunk)} words ({exc})")
                parts = []
            if len(parts) == len(chunk):
                out.update(dict(zip(chunk, parts)))
            else:
                # el bloque no cuadra: el motor ha juntado o partido lineas, y
                # emparejarlas a ciegas pondria cada palabra debajo de otra
                failed.extend(chunk)
        pending = failed
        if not pending:
            break
        log(f"{name} left {len(pending)} words untranslated; trying the next engine")
    if pending:
        # ultimo recurso: de una en una, lento pero salva lo que se pueda
        out.update(translate_terms(pending, source, target, log=log))
    return out


def translate_words(freq, tweets, project_dir, prefix, target="es", limit=100, log=print):
    """Devuelve la tabla de frecuencias con las palabras traducidas al idioma
    de quien analiza. Solo se traducen las que la nube llega a dibujar: son
    cien, no las mil de la tabla, y ese recorte es lo que hace que quepa en la
    cuota de un traductor gratuito.

    Las palabras que se repiten al traducir (el arabe distingue "marroqui" de
    "marroquies", el español no) suman sus frecuencias: la nube gana en vez de
    perder al fundirlas."""
    freq = freq.copy()
    if freq.empty:
        return freq
    if "word_src" not in freq.columns:
        freq["word_src"] = freq["word"]

    langs = [lang for lang in dominant_langs(tweets) if lang != target]
    if not langs:
        return freq
    source = langs[0]

    cache_path = project_dir / f"{prefix}{WORDS_SUFFIX}"
    cache = _read_cache_words(cache_path)
    known = {(row.word, row.lang): row.translation for row in cache.itertuples()}

    head = freq.head(limit)
    missing = [w for w in dict.fromkeys(head["word_src"]) if (w, source) not in known]
    if missing:
        log(f"Translating {len(missing)} cloud words {source} -> {target}")
        fresh = _translate_chunked(missing, source, target, log=log)
        rows = [{"word": w, "lang": source, "translation": t} for w, t in fresh.items()]
        if rows:
            pd.concat([cache, pd.DataFrame(rows)], ignore_index=True).to_csv(
                cache_path, index=False)
            log(f"Word translations saved to {cache_path.name}")
        known.update({(w, source): t for w, t in fresh.items()})

    translated = [known.get((src, source), "").strip() for src in freq["word_src"]]
    if not any(translated):
        return freq
    freq["word"] = [t.lower() if t else w for t, w in zip(translated, freq["word"])]

    # al traducir aparecen palabras vacias que antes no estaban: una palabra
    # arabe con contenido puede caer en "que" o en "en cierto modo". Se vuelve
    # a filtrar, ahora en el idioma de destino
    import charts_tweets
    stop = charts_tweets._stopwords()
    keep = [bool(word.split()) and not all(part in stop for part in word.split())
            for word in freq["word"]]
    freq = freq[keep]
    freq = (freq.groupby("word", as_index=False)
            .agg(freq=("freq", "sum"), word_src=("word_src", "|".join))
            .sort_values("freq", ascending=False)
            .reset_index(drop=True))
    freq.attrs["translated"] = (source, target)
    return freq


def _read_cache_words(path):
    if not path.exists():
        return pd.DataFrame(columns=["word", "lang", "translation"])
    cache = pd.read_csv(path, dtype=str).fillna("")
    for col in ("word", "lang", "translation"):
        if col not in cache.columns:
            cache[col] = ""
    return cache[["word", "lang", "translation"]]
