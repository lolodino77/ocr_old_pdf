"""Modernisation de texte par l'API Gemini (clé requise), alternative au LLM piloté dans le navigateur.

Deux modes sont disponibles pour l'utilisateur :
- **navigateur** (``browser_llm.py``) : aucune clé, mais une fenêtre Chrome et un poste avec écran ;
- **API** (ce module) : une clé API Gemini, aucun navigateur, utilisable sur un serveur (Streamlit Cloud).

La clé n'est **jamais écrite dans le code** : elle est lue dans cet ordre
1. celle saisie dans l'interface (``set_api_key``, gardée en mémoire seulement) ;
2. ``st.secrets["GEMINI_API_KEY"]`` (Streamlit Cloud), transmise par l'application ;
3. la variable d'environnement ``GEMINI_API_KEY`` (ou ``GOOGLE_API_KEY``) ;
4. le fichier ``.env`` à la racine du projet (``GEMINI_API_KEY=...``), ignoré par Git : voir ``.env.example``.

Le mode API peut aussi servir de **repli** quand le navigateur échoue (``set_fallback``).
Un site désigne soit un LLM du navigateur (« gemini », « gpt »), soit un modèle de l'API (« api:gemini-2.5-flash »).
"""
import os
import re
import time
from pathlib import Path

API_PREFIX = "api:"
API_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-2.5-flash-lite",
    "gemini-3-flash-preview",
    "gemini-3-pro-preview",
]
DEFAULT_MODEL = API_MODELS[0]
KEY_VARS = ("GEMINI_API_KEY", "GOOGLE_API_KEY")

_api_key = None
_fallback_model = None

# Erreurs passagères (serveur surchargé, quota, réseau) : on réessaie. Les autres (clé refusée, modèle inconnu) : non.
_RETRYABLE_RE = re.compile(
    r"\b(429|500|502|503|504)\b|UNAVAILABLE|RESOURCE_EXHAUSTED|overloaded|surcharg|deadline|time-?d? ?out|"
    r"connection|reset by peer|incomplète|vide",
    re.I,
)
_FATAL_RE = re.compile(
    r"API_KEY_INVALID|API key not valid|PERMISSION_DENIED|UNAUTHENTICATED|\b(400|401|403|404)\b|NOT_FOUND|"
    r"CERTIFICATE_VERIFY_FAILED",
    re.I,
)


def set_api_key(key):
    """Mémorise la clé saisie dans l'interface (None pour l'oublier)."""
    global _api_key
    _api_key = (key or "").strip() or None


ENV_FILE = Path(__file__).resolve().parent / ".env"


def _dotenv_value(var):
    """Valeur de ``var`` dans le fichier ``.env`` du projet (lignes ``NOM=valeur``, guillemets facultatifs)."""
    try:
        for line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            if name.strip().removeprefix("export ").strip() == var:
                return value.strip().strip("\"'").strip() or None
    except OSError:
        pass
    return None


def _env_key():
    """(valeur, origine) de la clé dans l'environnement du processus, puis dans le fichier .env."""
    for var in KEY_VARS:
        if os.environ.get(var, "").strip():
            return os.environ[var].strip(), f"variable d'environnement {var}"
    for var in KEY_VARS:
        value = _dotenv_value(var)
        if value:
            return value, f"fichier .env ({var})"
    return None, None


def get_api_key():
    return _api_key or _env_key()[0]


def key_source():
    """Origine de la clé pour l'affichage : « saisie », « variable GEMINI_API_KEY », « fichier .env »… ou None.
    Ne révèle jamais la clé."""
    if _api_key:
        return "saisie dans l'interface ou fournie par l'application"
    return _env_key()[1]


def set_fallback(model):
    """Modèle de l'API à utiliser en secours quand le navigateur échoue (None : pas de repli)."""
    global _fallback_model
    _fallback_model = model or None


def get_fallback():
    return _fallback_model


def spec(model):
    return API_PREFIX + model


def is_api(site):
    return str(site).startswith(API_PREFIX)


def model_of(site):
    return str(site)[len(API_PREFIX):]


def _redact(text, key):
    return text.replace(key, "***") if key else text


_certs_done = False


def _use_system_certificates():
    """Utilise le magasin de certificats du système si ``truststore`` est installé (antivirus ou proxy qui
    inspectent le HTTPS : sinon « CERTIFICATE_VERIFY_FAILED »)."""
    global _certs_done
    if not _certs_done:
        _certs_done = True
        try:
            import truststore

            truststore.inject_into_ssl()
        except ImportError:
            pass


def _generate(model, prompt, api_key, timeout_s):
    """Un appel à l'API Gemini (isolé pour pouvoir être remplacé dans les tests)."""
    _use_system_certificates()
    from google import genai

    try:
        from google.genai import types

        client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout_s * 1000)))
    except Exception:  # noqa: BLE001 - version de la bibliothèque sans HttpOptions
        client = genai.Client(api_key=api_key)
    return client.models.generate_content(model=model, contents=prompt).text or ""


def ask(model, prompt, api_key, timeout_s=300, waits=(10, 30, 60), counter=None):
    """Envoie ``prompt`` et renvoie la réponse nettoyée ; réessaie si le serveur est surchargé.

    ``counter`` : liste dans laquelle on ajoute un élément par appel réellement envoyé (compteur de prompts).
    """
    from browser_llm import END_MARKER, extract_answer

    for wait in (*waits, None):
        if counter is not None:
            counter.append(1)
        try:
            raw = _generate(model, prompt, api_key, timeout_s)
            if not raw.strip():
                raise RuntimeError("réponse vide")
            if END_MARKER not in raw:
                raise RuntimeError("réponse incomplète (ligne de fin absente)")
            return extract_answer(raw)
        except Exception as exc:  # noqa: BLE001
            message = _redact(f"{type(exc).__name__}: {exc}", api_key)
            if "CERTIFICATE_VERIFY_FAILED" in message:
                message += " (antivirus ou proxy qui inspecte le HTTPS ? installez `pip install truststore`)"
            if wait is None or (_FATAL_RE.search(message) and not _RETRYABLE_RE.search(message)):
                raise RuntimeError(message) from None
            print(f"Échec API ({message[:150]}) : nouvel essai dans {wait} s", flush=True)
            time.sleep(wait)


def run_batch(model, prompts, timeout_s=300, api_key=None):
    """Envoie les prompts un par un. Retourne ``{"answers": [...], "prompts_sent": n, "error": "..."}``.

    Même contrat que le sous-processus du navigateur : un morceau en échec donne ``None`` sans arrêter les
    autres ; une clé refusée arrête tout (inutile d'insister) ; deux échecs de suite arrêtent aussi.
    """
    api_key = api_key or get_api_key()
    n = len(prompts)
    if not api_key:
        return {"answers": [None] * n, "prompts_sent": 0,
                "error": "clé API Gemini introuvable : définissez la variable d'environnement GEMINI_API_KEY "
                         "(ou saisissez la clé dans l'interface)"}
    counter, answers, errors = [], [], {}
    for i, prompt in enumerate(prompts, start=1):
        if len(errors) >= 2 and all(k in errors for k in (i - 2, i - 1)):
            answers.append(None)
            errors[i] = "non envoyé (échecs précédents)"
            continue
        print(f"Modernisation du morceau {i}/{n} via {API_PREFIX}{model} ...", flush=True)
        try:
            answers.append(ask(model, prompt, api_key, timeout_s, counter=counter))
        except RuntimeError as exc:
            answers.append(None)
            errors[i] = str(exc)
            if _FATAL_RE.search(str(exc)) and not _RETRYABLE_RE.search(str(exc)):
                answers.extend([None] * (n - i))
                errors.update({k: "non envoyé (erreur définitive)" for k in range(i + 1, n + 1)})
                break
    out = {"answers": answers, "prompts_sent": len(counter)}
    if errors:
        out["error"] = f"morceau(x) {', '.join(map(str, errors))} en échec : {next(iter(errors.values()))}"
    return out
