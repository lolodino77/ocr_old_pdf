"""Contrôles qualité de la modernisation, sans appel au LLM.

- par morceau : passages de l'OCR absents de la réponse (omissions), crochets ajoutés (ajouts) ;
- entre morceaux (continuité) : mots répétés de part et d'autre d'une jointure, phrase tronquée,
  ponctuation ajoutée au milieu d'une phrase, contexte (CONTEXTE PRÉCÉDENT / SUITE) recopié ;
- sur le texte final : graphies anciennes restantes.

Les textes sont comparés mot à mot après normalisation (accents, s long et « f » de l'OCR, y/i, u/v,
terminaisons -oit…), pour qu'un mot ancien et sa forme moderne soient considérés comme identiques.
"""
import difflib
import re
import unicodedata

_WORD_RE = re.compile(r"[^\W\d_]+|&")
_FINAL_PUNCT_RE = re.compile(r"[.!?:»”\")]$")

ARCHAIC_RE = re.compile(
    r"\b(estoit|estoient|seroit|seroient|avoit|avoient|moy|toy|soy|cecy|celuy|ainsy|aussy|sçay|sçait|"
    r"sçavoir|nostre|vostre|estes|mesme|mesmes|j'ay|ay|fay|treuve|reprens|ayme|aymé|playe|playes|"
    r"recognoistre|cognoistre|connoistre|paroistre|aumosne|eft|eftre|Verf|adjoute|adjouste|jusques|"
    r"pource|long-temps|vn|vne)\b",
    re.I,
)
# Terminaisons -oit / -oient restées anciennes (les mots modernes en -oit sont exclus)
_MODERN_OIT = {
    "droit", "doit", "soit", "voit", "croit", "toit", "exploit", "endroit", "étroit", "adroit", "reçoit",
    "aperçoit", "conçoit", "déçoit", "pourvoit", "prévoit", "revoit", "soient", "doivent", "boit", "emboit",
    "pourvoient", "voient", "croient", "aperçoivent", "envoit", "renvoit", "foi", "exploit", "emploient",
    "perçoit", "entrevoit", "sursoit", "déploient", "nettoient", "noient", "aboient", "côtoient", "rudoient",
}
_OLD_OIT_RE = re.compile(r"\b\w+(?:oit|oient)\b")


def norm_word(word):
    if word == "&":
        return "et"
    w = unicodedata.normalize("NFD", word.lower())
    w = "".join(c for c in w if unicodedata.category(c) != "Mn")
    w = w.replace("ſ", "s").replace("f", "s").replace("y", "i").replace("v", "u").replace("j", "i")
    w = re.sub(r"oi(t|ent|s)$", r"ai\1", w)
    w = re.sub(r"s(?=[tcpqm])", "", w)  # s muet ancien : estoit, mesme
    return re.sub(r"(.)\1", r"\1", w)  # consonnes doublées


def words(text):
    """Liste de (début, fin, mot normalisé) pour chaque mot de ``text``."""
    return [(m.start(), m.end(), norm_word(m.group())) for m in _WORD_RE.finditer(text)]


def norm_words(text):
    return [w for _, _, w in words(text)]


# --- Contrôles par morceau -------------------------------------------------------------------------

def _is_ocr_noise(span):
    """Vrai si le passage est surtout fait de fragments de 1 à 3 lettres (bruit d'OCR, pas du texte)."""
    tokens = _WORD_RE.findall(span)
    return not tokens or sum(len(t) >= 4 for t in tokens) < 0.3 * len(tokens)


def check_chunk(source, answer, min_words=20):
    """Compare un morceau de l'OCR et sa réponse modernisée.

    Retourne ``{"coverage": part des mots de l'OCR retrouvés, "missing": [passages OCR absents],
    "added": [crochets absents de l'OCR]}``. Un passage manquant fait au moins ``min_words`` mots et
    n'est remplacé par presque rien dans la réponse (les en-têtes de page supprimés sont plus courts).
    """
    src, ans = words(source), norm_words(answer)
    a = [w for _, _, w in src]
    sm = difflib.SequenceMatcher(None, a, ans, autojunk=False)
    matched = sum(block.size for block in sm.get_matching_blocks())
    opcodes = sm.get_opcodes()
    # Mots de la réponse qui ne correspondent à rien dans l'OCR : un passage déplacé par le LLM s'y retrouve.
    unmatched = [w for tag, _i1, _i2, j1, j2 in opcodes if tag in ("insert", "replace") for w in ans[j1:j2]]
    missing = []
    for tag, i1, i2, j1, j2 in opcodes:
        if tag in ("delete", "replace") and i2 - i1 >= min_words and (j2 - j1) < 0.3 * (i2 - i1):
            # Passage déplacé par le LLM (lignes de l'OCR remises dans l'ordre) : présent ailleurs, pas omis.
            # Cherché seulement dans les mots de la réponse restés sans correspondance : un passage omis dont le
            # texte se répète plus loin dans l'original (verset cité deux fois) n'est pas pris pour un passage
            # déplacé (constaté). Seuls les groupes d'au moins 2 mots comptent.
            moved = difflib.SequenceMatcher(None, a[i1:i2], unmatched, autojunk=False)
            if sum(b.size for b in moved.get_matching_blocks() if b.size >= 2) >= 0.3 * (i2 - i1):
                continue
            span = source[src[i1][0]:src[i2 - 1][1]]
            if _is_ocr_noise(span):  # ornements, gravures lus comme des lettres : le LLM a raison de les retirer
                continue
            missing.append(re.sub(r"\s+", " ", span))
    added = [] if "[" in source else re.findall(r"\[[^\]]*\]", answer)
    return {"coverage": matched / len(a) if a else 1.0, "missing": missing, "added": added}


# --- Contrôles de continuité entre morceaux -------------------------------------------------------

def overlap_words(previous, following, max_words=30):
    """Nombre de mots identiques (normalisés) entre la fin de ``previous`` et le début de ``following``."""
    a, b = norm_words(previous[-800:]), norm_words(following[:800])
    for k in range(min(max_words, len(a), len(b)), 0, -1):
        if a[-k:] == b[:k]:
            return k
    return 0


def _copied_from(answer_words, context, own, min_words=6):
    """Vrai si ``answer_words`` reprend au moins ``min_words`` mots du contexte, plus que du morceau lui-même."""
    def longest(target):
        sm = difflib.SequenceMatcher(None, answer_words, norm_words(target), autojunk=False)
        return sm.find_longest_match(0, len(answer_words), 0, len(sm.b)).size

    in_context = longest(context)
    return in_context >= min_words and in_context > longest(own)


def ends_on_sentence(chunk):
    """Vrai si le morceau d'origine se termine par une fin de phrase (avant d'éventuelles lignes vides)."""
    return bool(re.search(r"[.!?][»”\")]*\s*$", chunk))


# Types de problèmes de jointure : ceux que join_chunks corrige seul, et ceux qui demandent de renvoyer
# le prompt du morceau fautif.
AUTO_FIXED = {"doublon", "point_ajoute"}


def check_junctions(chunks, answers, context_chars=400):
    """Contrôle la continuité entre réponses consécutives.

    Retourne une liste de ``{"kind", "chunk", "message"}`` ; ``chunk`` est l'indice du morceau à renvoyer
    au LLM pour corriger le problème (types hors de ``AUTO_FIXED``).
    """
    issues = []

    def add(kind, chunk, message):
        issues.append({"kind": kind, "chunk": chunk, "message": message})

    for i in range(len(answers) - 1):
        prev, nxt = answers[i].strip(), answers[i + 1].strip()
        label = f"jointure {i + 1}/{i + 2}"
        if not prev or not nxt:
            add("vide", i if not prev else i + 1, f"{label} : réponse vide")
            continue
        k = overlap_words(prev, nxt)
        if k:
            add("doublon", i, f"{label} : {k} mot(s) répété(s) de part et d'autre (« …{prev[-50:]} » / « {nxt[:50]}… »)")
        prev_final = bool(_FINAL_PUNCT_RE.search(prev))
        prev_sentence_end = bool(re.search(r"[.!?][»”\")]*$", prev))  # « : » peut être suivi d'une minuscule
        next_upper = nxt[0].isupper() or nxt[0] in "«“\"("
        if ends_on_sentence(chunks[i]) and not prev_final:
            add("phrase_tronquee", i, f"{label} : phrase tronquée en fin de morceau {i + 1} (« …{prev[-60:]} »)")
        if prev_sentence_end and not next_upper and not k:
            add("point_ajoute", i, f"{label} : point ajouté au milieu d'une phrase (« …{prev[-40:]} » / « {nxt[:40]}… »)")
        tail, head = norm_words(prev)[-12:], norm_words(nxt)[:12]
        if _copied_from(tail, chunks[i + 1][:context_chars], chunks[i]):
            add("suite_recopiee", i, f"{label} : la SUITE (contexte) a été recopiée en fin de morceau {i + 1}")
        if _copied_from(head, chunks[i][-context_chars:], chunks[i + 1]):
            add("contexte_recopie", i + 1, f"{label} : le CONTEXTE PRÉCÉDENT a été recopié en début de morceau {i + 2}")
    return issues


# --- Contrôle du texte final ------------------------------------------------------------------------

def residual_archaic(text):
    """Graphies anciennes restantes : ``{forme: nombre}``."""
    found = [m.group(1).lower() for m in ARCHAIC_RE.finditer(text)]
    found += [
        w.lower() for w in _OLD_OIT_RE.findall(text) if w.lower() not in _MODERN_OIT and not ARCHAIC_RE.fullmatch(w)
    ]
    counts = {}
    for w in found:
        counts[w] = counts.get(w, 0) + 1
    return counts
