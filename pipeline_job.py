"""Traitement lancé en arrière-plan, indépendant de la page du navigateur.

Avant : tout le traitement tournait dans le script Streamlit de la session du navigateur. Si cette session se
perdait (connexion coupée, onglet endormi ou rechargé, veille de l'ordinateur, simple clic sur un autre bouton),
le traitement s'arrêtait et la page repartait de zéro. Pour un PDF de 700 pages (plusieurs heures), c'est
inévitable tôt ou tard.

Maintenant : le traitement est un fil d'exécution du serveur, sans lien avec la page. La page ne fait que
l'afficher (``Job.snapshot``) ; après un rechargement, la nouvelle page retrouve le traitement en cours et reprend
son affichage. Aucun appel Streamlit ici : seulement des données lues par la page.
"""
import threading
import time
import traceback


class Job:
    def __init__(self, documents):
        self.documents = list(documents)
        self.lock = threading.Lock()
        self.started = time.time()
        self.finished = None  # instant de fin, ou None tant que le traitement tourne
        self.pct, self.progress_text = 0, "⏳ Démarrage du traitement ..."
        self.messages = []  # (niveau, texte) : « info », « warning », « error », « title »
        self.last = ("info", "")
        self.generated = {"docx": [], "pdf": [], "markdown": []}
        self.single_word_file = None
        self.run_log = None
        self.errors = 0

    # --- écriture (fil de traitement) ---
    def log(self, level, text):
        with self.lock:
            self.last = (level, text)
            self.messages.append((level, text))

    def set_progress(self, pct, text):
        with self.lock:
            self.pct, self.progress_text = pct, text

    def done(self):
        with self.lock:
            self.finished = time.time()

    # --- lecture (page) ---
    @property
    def running(self):
        return self.finished is None

    def snapshot(self):
        with self.lock:
            return {
                "pct": self.pct, "text": self.progress_text, "last": self.last, "running": self.finished is None,
                "messages": list(self.messages), "generated": {k: list(v) for k, v in self.generated.items()},
                "errors": self.errors, "run_log": self.run_log,
            }


class _Slot:
    """Même interface que ``st.empty()`` pour PipelineProgressBar, mais écrit dans le Job."""

    def __init__(self, job):
        self._job = job

    def progress(self, pct, text=""):
        self._job.set_progress(pct, text)
        return self


_current = None
_start_lock = threading.Lock()


def current():
    return _current


def slot_for(job):
    return _Slot(job)


def start(job, target):
    """Lance ``target(job)`` dans un fil du serveur. Refuse s'il y en a déjà un qui tourne."""
    global _current
    with _start_lock:
        if _current is not None and _current.running:
            return False
        _current = job

    def run():
        try:
            target(job)
        except BaseException as exc:  # noqa: BLE001 - la page doit toujours pouvoir afficher la fin
            traceback.print_exc()
            job.errors += 1
            job.log("error", f"❌ Le traitement s'est arrêté : {exc}")
        finally:
            job.done()

    threading.Thread(target=run, name="traitement", daemon=True).start()
    return True
