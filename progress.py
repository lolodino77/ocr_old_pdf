"""Signaux d'avancement du pipeline, sans dépendre de Streamlit.

Les étapes (conversion des pages, OCR, envoi des morceaux au LLM) appellent ``report(done, total, detail)`` ;
l'interface (app.py) s'abonne avec ``set_callback`` et affiche le pourcentage. Sans abonné, rien ne se passe :
les scripts en ligne de commande et les tests ne sont pas concernés.

L'étape courante (``set_stage``) est fixée par l'appelant : une même fonction (run_prompts) sert au premier envoi
des morceaux et aux renvois des morceaux fautifs, qui n'ont pas le même poids dans la barre.
"""
_callback = None
_stage = None


def set_callback(callback):
    """``callback(stage, done, total, detail)`` ; None pour se désabonner."""
    global _callback
    _callback = callback


def set_stage(stage):
    global _stage
    _stage = stage


CHUNK_EXPECTED_S = 75  # durée habituelle d'une réponse du LLM pour un morceau (navigateur ou API)


def chunk_waiting(i, total, waited_s):
    """Pendant l'attente de la réponse au morceau ``i`` (1 à ``total``) : progression estimée d'après le temps
    écoulé, plafonnée à 90 % du morceau tant que la réponse n'est pas arrivée (comme la barre des appels LLM en
    streaming de cv-builder, plafonnée à 99 %). Sans cela, la barre resterait figée une minute par morceau."""
    fraction = min(0.9, waited_s / CHUNK_EXPECTED_S)
    report(i - 1 + fraction, total, f"morceau {i}/{total}, réponse en attente depuis {int(waited_s)} s")


def report(done, total, detail=""):
    if _callback is None or _stage is None:
        return
    try:
        _callback(_stage, done, total, detail)
    except Exception:  # noqa: BLE001 - l'affichage de l'avancement ne doit jamais faire échouer le traitement
        pass
