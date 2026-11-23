"""Modernisation de texte par un LLM en ligne gratuit piloté dans un vrai navigateur (Gemini, ChatGPT).

Principe (repris des projets generate-fr-subtitles-from-chinese / auto-wordpress-translator) : Playwright
ouvre Chrome (ou Edge) avec un **profil persistant** (connexion manuelle une seule fois, voir
``python browser_llm.py login``), colle le prompt dans la zone de saisie du site, l'envoie, puis lit la
réponse dans le dernier bloc de code de la page. La réponse est complète quand elle contient une ligne de
fin (``END_MARKER``).

Limites : les sélecteurs CSS (``SITES``) dépendent de l'interface des sites et peuvent casser ; seul ce
dictionnaire est alors à adapter. Captchas et connexions ne sont jamais contournés : la fenêtre reste
visible pour que vous les traitiez. Nécessite un navigateur graphique : ne fonctionne pas sur un serveur
sans écran (Streamlit Cloud).
"""
import os
import re
import sys
import time
from pathlib import Path

from quality_checks import overlap_words, words

END_MARKER = "###FIN###"

# Sélecteurs séparés par des virgules (le premier qui correspond est utilisé).
SITES = {
    "gemini": {
        "url": "https://gemini.google.com/app",
        "input": "div.ql-editor[contenteditable='true'], rich-textarea div[contenteditable='true']",
        "code": "code-block code, pre code",
        "reply": "message-content, .model-response-text",
    },
    "gpt": {
        "url": "https://chatgpt.com/",
        "input": "#prompt-textarea, textarea[data-testid='prompt-textarea']",
        "code": "pre code",
        "reply": "[data-message-author-role='assistant']",
    },
}

_REFUSE_RE = re.compile(r"tout refuser|reject all|refuser|rester déconnecté|stay logged out|non merci|no thanks", re.I)
_ERROR_RE = re.compile(
    r"something went wrong|une erreur est survenue|you've reached|vous avez atteint|try again later|"
    r"réessayez plus tard|too many requests|trop de requêtes|capacity|surcharg",
    re.I,
)


_REFUSAL_RE = re.compile(
    r"je ne peux pas (?:vous )?aider|je ne suis qu'un modèle de langage|I can't help with|I'm (?:just|only) a language model",
    re.I,
)


class BrowserLLMUnavailable(Exception):
    """Le service ne peut pas être utilisé (déconnecté, captcha, quota, interface modifiée, navigateur)."""


def default_profile_dir():
    """Profil du navigateur : hors du dépôt (il contient des cookies de connexion)."""
    return Path(os.environ.get("OCR_BROWSER_PROFILE") or Path.home() / ".ocr_old_pdf" / "browser_profile")


class BrowserSession:
    """Chrome piloté par Playwright, profil persistant, fenêtre visible (connexion et captcha manuels)."""

    def __init__(self, profile_dir=None, channel="chrome", headless=False):
        self.profile_dir = Path(profile_dir) if profile_dir else default_profile_dir()
        self.channel = channel
        self.headless = headless
        self._pw = None
        self._ctx = None
        self.prompts_sent = 0  # prompts réellement envoyés au site (réessais compris)

    def open(self):
        if self._ctx is not None:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BrowserLLMUnavailable("Playwright n'est pas installé (pip install playwright)") from exc
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()
        last = None
        for channel in dict.fromkeys([self.channel, "msedge", ""]):  # Chrome, puis Edge, puis Chromium de Playwright
            try:
                kwargs = {"headless": self.headless, "viewport": {"width": 1280, "height": 900}}
                if channel:
                    kwargs["channel"] = channel
                self._ctx = self._pw.chromium.launch_persistent_context(str(self.profile_dir), **kwargs)
                self._ctx.set_default_timeout(60000)  # aucune action Playwright ne doit attendre indéfiniment
                return
            except Exception as exc:  # noqa: BLE001 - essai du navigateur suivant
                last = exc
        self.close()
        raise BrowserLLMUnavailable(f"Aucun navigateur utilisable : {last}")

    def close(self):
        for obj, method in ((self._ctx, "close"), (self._pw, "stop")):
            try:
                if obj is not None:
                    getattr(obj, method)()
            except Exception:  # noqa: BLE001
                pass
        self._ctx = self._pw = None

    def login(self, sites):
        """Ouvre chaque site dans un onglet ; l'utilisateur se connecte à la main puis valide dans la console."""
        self.open()
        for site in sites:
            self._ctx.new_page().goto(SITES[site]["url"], wait_until="domcontentloaded")
        input("Connectez-vous à vos comptes dans les onglets ouverts, puis appuyez sur Entrée… ")

    @staticmethod
    def _dismiss_banners(page):
        """Refuse bannières et cookies ; n'accepte jamais rien."""
        try:
            page.get_by_role("button", name=_REFUSE_RE).first.click(timeout=3000)
            page.wait_for_timeout(800)
        except Exception:  # noqa: BLE001 - pas de bannière
            pass

    @staticmethod
    def _last_text(page, selector):
        try:
            loc = page.locator(selector)
            n = loc.count()
            return loc.nth(n - 1).inner_text() if n else ""
        except Exception:  # noqa: BLE001
            return ""

    def ask(self, site, prompt, timeout_s=300):
        """Envoie ``prompt`` au site et renvoie le texte brut de la réponse complète."""
        if site not in SITES:
            raise BrowserLLMUnavailable(f"Site inconnu : {site}")
        cfg = SITES[site]
        self.open()
        page = self._ctx.new_page()
        try:
            try:
                page.goto(cfg["url"], wait_until="domcontentloaded", timeout=60000)
            except Exception as exc:  # noqa: BLE001 - réseau lent : on laisse ask_with_retries réessayer
                raise BrowserLLMUnavailable(f"{site} : la page ne se charge pas ({exc})") from exc
            try:
                page.wait_for_selector(cfg["input"], timeout=60000)
            except Exception as exc:  # noqa: BLE001
                raise BrowserLLMUnavailable(
                    f"{site} : zone de saisie introuvable (déconnecté ? captcha ? interface modifiée ? "
                    "lancez « python browser_llm.py login »)"
                ) from exc
            self._dismiss_banners(page)
            for attempt in (1, 2):
                try:
                    page.locator(cfg["input"]).first.click()
                    page.keyboard.insert_text(prompt)  # d'un bloc (pas de frappe caractère par caractère)
                    page.wait_for_timeout(1500)
                    page.keyboard.press("Enter")
                    self.prompts_sent += 1
                    break
                except Exception as exc:  # noqa: BLE001
                    if attempt == 2:
                        raise BrowserLLMUnavailable(f"{site} : envoi impossible ({exc})") from exc
                    page.wait_for_timeout(3000)
            return self._wait_answer(page, site, cfg, timeout_s)
        finally:
            try:
                page.close()
            except Exception:  # noqa: BLE001
                pass

    def _wait_answer(self, page, site, cfg, timeout_s):
        start = time.monotonic()
        while time.monotonic() - start < timeout_s:
            for key in ("code", "reply"):
                text = self._last_text(page, cfg[key])
                if END_MARKER in text:
                    return text
            reply = self._last_text(page, cfg["reply"])
            if time.monotonic() - start > 20 and _REFUSAL_RE.search(reply):
                # Refus du modèle : inutile d'attendre la ligne de fin, une nouvelle conversation répond souvent
                raise BrowserLLMUnavailable(f"{site} : refus du modèle (« {reply.strip()[:120]} »)")
            if time.monotonic() - start > 45 and not self._last_text(page, cfg["reply"]):
                try:
                    body = page.inner_text("body")
                except Exception:  # noqa: BLE001
                    body = ""
                if _ERROR_RE.search(body):
                    raise BrowserLLMUnavailable(f"{site} : message d'erreur ou de limite affiché")
            page.wait_for_timeout(3000)
        seen = (self._last_text(page, cfg["reply"]) or self._last_text(page, cfg["code"]))[-300:].replace("\n", " ⏎ ")
        raise BrowserLLMUnavailable(
            f"{site} : pas de réponse complète en {timeout_s} s (dernier texte vu : « {seen or 'aucun'} »)"
        )


_UI_LABELS = {
    "", "text", "txt", "markdown", "plaintext", "plain text", "texte", "extrait de code", "code snippet",
    "copier le code", "copy code", "code",
}


def extract_answer(raw):
    """Texte de la réponse sans les ``` éventuels ni la ligne de fin."""
    text = raw.split(END_MARKER)[0].replace("```", "")
    # L'interface ajoute en tête du bloc de code son langage (« text », « markdown ») ou une étiquette
    # (« Extrait de code », constaté sur Gemini) : ces lignes ne font pas partie de la réponse
    lines = text.strip("\n").splitlines()
    while lines and lines[0].strip().lower() in _UI_LABELS:
        lines = lines[1:]
    return "\n".join(lines).strip()


# Abréviations après lesquelles un point ne termine pas la phrase (références bibliques, titres…)
_ABBREVIATIONS = {
    "s", "st", "ste", "m", "mr", "mm", "chap", "ch", "vers", "verf", "v", "ps", "pf", "act", "rom", "cor", "gal",
    "eph", "phil", "col", "thess", "tim", "tit", "hebr", "heb", "jaq", "pier", "apoc", "matth", "matt", "luc",
    "marc", "jean", "gen", "exod", "deut", "esa", "jer", "ezech", "dan", "etc", "cf", "p", "pag", "liv", "art",
    # titres des notes en marge (Proposition, Exorde, Application…), constatés dans les éditions de Nardin
    "prop", "exord", "appl", "applic", "part", "sect", "obj", "rep", "conf", "n", "no",
}
_SENTENCE_END_RE = re.compile(r"(\w+)[.!?][»”\")]*(\s+)(?=[«“\"(]?[A-ZÀ-ÖØ-Þ])")
_LINE_END_RE = re.compile(r"[^\s-][ \t]*\n")  # fin de ligne sans césure


def _is_sentence_end(match):
    word = match.group(1)
    return (
        len(word) >= 2
        and word.lower() not in _ABBREVIATIONS
        and not word.isdigit()
        and not re.fullmatch(r"[IVXLCDM]+", word)  # numéro de chapitre ou de verset
    )


def _best_cut(text, max_chars):
    """Position de coupe dans ``text[:max_chars]`` qui évite de séparer une phrase ou un mot.

    Par ordre de préférence, dans la seconde moitié de la fenêtre : fin de phrase suivie d'une ligne vide,
    fin de phrase, fin de ligne sans césure ; à défaut, coupe brute. Sur un texte OCR la détection n'est
    pas infaillible : le contexte joint à chaque prompt (voir ocr_text_to_modernized_text) couvre le reste.
    """
    window, start = text[:max_chars], max_chars // 2
    sentences = [m for m in _SENTENCE_END_RE.finditer(window) if m.end() >= start and _is_sentence_end(m)]
    paragraph = [m.end() for m in sentences if m.group(2).count("\n") >= 2]
    if paragraph:
        return paragraph[-1]
    if sentences:
        return sentences[-1].end()
    line = [m.end() for m in _LINE_END_RE.finditer(window) if m.end() >= start]
    return line[-1] if line else max_chars


def split_in_chunks(text, max_chars=6000):
    """Découpe ``text`` en blocs d'au plus ``max_chars`` caractères, sans couper une phrase entre deux blocs.

    Les blocs mis bout à bout redonnent exactement ``text``.
    """
    chunks, rest = [], text
    while len(rest) > max_chars:
        cut = _best_cut(rest, max_chars)
        chunks.append(rest[:cut])
        rest = rest[cut:]
    if rest.strip():
        chunks.append(rest)
    return chunks


def join_chunks(chunks, answers):
    """Recolle les réponses des blocs.

    Saut de paragraphe seulement si le bloc d'origine finissait par une fin de phrase suivie d'une ligne
    vide ET que la réponse finit par une ponctuation finale ; sinon la phrase continue (espace).
    """
    text = ""
    for i, answer in enumerate(answers):
        answer = answer.strip()
        if i:
            paragraph = re.search(r"[.!?:»”\")]\s*\n[ \t]*\n\s*$", chunks[i - 1]) and re.search(r"[.!?:»”\")]$", text)
            # Mots en double de part et d'autre de la jointure (réclame de bas de page, contexte recopié) :
            # on les retire de la fin du morceau précédent, ponctuation ajoutée comprise.
            k = overlap_words(text, answer)
            # Répétition présente dans le texte d'origine : on la garde, sauf la réclame (un mot seul sur la
            # dernière ligne de la page, répété en tête de la suivante)
            reclame = k == 1 and re.search(r"\n[ \t]*[^\s]+[ \t]*$", chunks[i - 1].rstrip())
            if k and not reclame and overlap_words(chunks[i - 1], chunks[i]) >= k:
                k = 0
            if k:
                text, paragraph = text[:words(text)[-k][0]].rstrip(), False
            elif re.search(r"[.!?]$", text) and answer[:1].islower():
                # Point ajouté par le LLM à une phrase que la découpe a coupée : la phrase continue
                text, paragraph = text[:-1], False
            text += "\n\n" if paragraph else " "
        text += answer
    return text


def ask_with_retries(session, site, prompt, timeout_s=300, waits=(10, 30)):
    """Envoie le prompt ; en cas d'échec (coupure réseau, page lente…), réessaie après chaque attente de ``waits``."""
    for wait in (*waits, None):
        try:
            return extract_answer(session.ask(site, prompt, timeout_s))
        except Exception as exc:  # noqa: BLE001 - erreur Playwright imprévue : on réessaie aussi
            if wait is None:
                raise
            print(f"Échec ({exc}) : nouvel essai dans {wait} s", flush=True)
            time.sleep(wait)


LOG_DIR = Path(__file__).resolve().parent / "logs"
_run_log = None
_run_total = 0


def start_run_log():
    """Crée un nouveau fichier logs/run_AAAAMMJJ_HHMMSS.log pour cette exécution et remet le compteur à zéro."""
    global _run_log, _run_total
    LOG_DIR.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    _run_log = LOG_DIR / f"run_{stamp}.log"
    n = 1
    while _run_log.exists():  # deux exécutions dans la même seconde
        n += 1
        _run_log = LOG_DIR / f"run_{stamp}_{n}.log"
    _run_total = 0
    write_log("Début de l'exécution")
    return _run_log


def write_log(message):
    if _run_log is None:
        start_run_log()
    with open(_run_log, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {message}\n")


def log_prompts(document, site, chunks, sent, error=None):
    """Consigne le nombre de prompts envoyés pour un document, et le total de l'exécution."""
    global _run_total
    _run_total += sent
    status = f"ERREUR : {error}" if error else "OK"
    write_log(
        f"document={document} | site={site} | morceaux={chunks} | prompts_envoyes={sent} "
        f"| total_execution={_run_total} | {status}"
    )


def run_prompts(site, prompts, timeout_s=300, document="", allow_partial=False):
    """Envoie les prompts à ``site`` et renvoie les réponses nettoyées (une par prompt).

    Le nombre de prompts réellement envoyés (réessais compris) est consigné dans le log de l'exécution
    (``logs/``, voir ``start_run_log``). Avec ``allow_partial``, un prompt en échec donne ``None`` au lieu
    de faire échouer l'ensemble (sauf si tous échouent).

    Playwright tourne dans un **sous-processus** : il a besoin d'une boucle asyncio capable de lancer des
    processus, ce que le thread de Streamlit n'offre pas sous Windows (NotImplementedError).
    """
    import json
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp) / "prompts.json", Path(tmp) / "answers.json"
        src.write_text(json.dumps(prompts, ensure_ascii=False), encoding="utf-8")
        # Durée maximale : chaque prompt peut épuiser son délai et ses nouveaux essais. Au-delà, le navigateur
        # est considéré comme bloqué (constaté : sous-processus figé plus d'une heure) et il est arrêté.
        max_s = len(prompts) * 3 * (timeout_s + 100) + 120
        try:
            proc = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "batch", site, str(src), str(dst), str(timeout_s)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=max_s,
            )
        except subprocess.TimeoutExpired:
            error = f"navigateur bloqué : aucune fin après {max_s} s, sous-processus arrêté"
            log_prompts(document, site, len(prompts), 0, error + " (prompts envoyés inconnus)")
            raise BrowserLLMUnavailable(error)
        if proc.stdout:
            print(proc.stdout, end="")
        if not dst.exists():
            error = f"Le sous-processus navigateur a échoué : {proc.stderr[-500:]}"
            log_prompts(document, site, len(prompts), 0, error + " (prompts envoyés inconnus)")
            raise BrowserLLMUnavailable(error)
        result = json.loads(dst.read_text(encoding="utf-8"))
    log_prompts(document, site, len(prompts), result.get("prompts_sent", 0), result.get("error"))
    answers = result.get("answers") or []
    if "error" in result and not (allow_partial and any(a is not None for a in answers)):
        raise BrowserLLMUnavailable(result["error"])
    return answers


def _batch(site, src, dst, timeout_s):
    import json

    prompts = json.loads(Path(src).read_text(encoding="utf-8"))
    session = BrowserSession()
    answers, errors = [], {}
    try:
        for i, prompt in enumerate(prompts, start=1):
            if len(errors) >= 2 and all(k in errors for k in (i - 2, i - 1)):
                # Deux échecs de suite : panne probable (réseau, navigateur), inutile d'insister
                answers.append(None)
                errors[i] = "non envoyé (échecs précédents)"
                continue
            print(f"Modernisation du morceau {i}/{len(prompts)} via {site} ...", flush=True)
            try:
                answers.append(ask_with_retries(session, site, prompt, timeout_s))
            except Exception as exc:  # noqa: BLE001 - un morceau en échec n'arrête pas les autres
                answers.append(None)
                errors[i] = str(exc)
    finally:
        session.close()
    out = {"answers": answers, "prompts_sent": session.prompts_sent}
    if errors:
        first = next(iter(errors.values()))
        out["error"] = f"morceau(x) {', '.join(map(str, errors))} en échec : {first}"
    Path(dst).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "login":
        s = BrowserSession()
        try:
            s.login(sys.argv[2:] or list(SITES))
        finally:
            s.close()
    elif len(sys.argv) == 6 and sys.argv[1] == "batch":
        _batch(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]))
    else:
        print("Usage : python browser_llm.py login [gemini] [gpt]")
