"""Tests hors ligne (sans navigateur) de la découpe, du recollage et des contrôles qualité.

Lancer : python test_quality_checks.py   (ou pytest test_quality_checks.py)
"""
from browser_llm import join_chunks, split_in_chunks
from quality_checks import check_chunk, check_junctions, residual_archaic

SENTENCE = "Il est vrai que le present des Philippiens estoit peu de chose a le regarder en luy mesme. "


def kinds(issues):
    return sorted(i["kind"] for i in issues)


# --- Découpe ----------------------------------------------------------------------------------------

def test_split_is_lossless_and_bounded():
    text = (SENTENCE * 40 + "\n\n") * 5
    chunks = split_in_chunks(text, max_chars=1500)
    assert "".join(chunks) == text
    assert all(len(c) <= 1500 for c in chunks)


def test_split_cuts_at_sentence_end():
    text = SENTENCE * 60
    for chunk in split_in_chunks(text, max_chars=1000)[:-1]:
        assert chunk.rstrip().endswith("mesme."), repr(chunk[-40:])


def test_split_ignores_abbreviations_and_roman_numerals():
    # Les seules « fins de phrase » de la seconde moitié sont des abréviations : la coupe se fait en fin de ligne
    text = "mot " * 120 + "\nselon S. Paul et Chap. III. Vers. X. Il dit\nque " + "mot " * 200
    first = split_in_chunks(text, max_chars=700)[0]
    for bad in ("S. ", "Chap. ", "III. ", "X. "):
        assert not first.endswith(bad), repr(first[-30:])


def test_split_never_cuts_after_hyphenation():
    text = ("abbai-\nssé " * 300)
    for chunk in split_in_chunks(text, max_chars=500)[:-1]:
        assert not chunk.rstrip().endswith("-"), repr(chunk[-20:])


# --- Recollage --------------------------------------------------------------------------------------

def test_join_removes_catchword_duplicate():
    chunks = ["…les jugemens de\n\nDieu\n\n", "Dieu par repentance."]
    answers = ["Prévenons donc les jugements de Dieu.", "Dieu par repentance. Relevons nos mains."]
    assert join_chunks(chunks, answers) == "Prévenons donc les jugements de Dieu par repentance. Relevons nos mains."


def test_join_removes_multi_word_overlap():
    chunks = ["a b c. ", "d e f."]
    answers = ["Il faut aimer Dieu de tout son cœur.", "Dieu de tout son cœur. Et son prochain."]
    assert join_chunks(chunks, answers) == "Il faut aimer Dieu de tout son cœur. Et son prochain."


def test_join_removes_period_added_mid_sentence():
    chunks = ["la grâce de\n", "Dieu nous suffit."]
    answers = ["Car la grâce.", "de Dieu nous suffit."]
    assert join_chunks(chunks, answers) == "Car la grâce de Dieu nous suffit."


def test_join_keeps_paragraphs_and_sentences():
    chunks = ["Fin du paragraphe.\n\n", "Nouveau paragraphe."]
    assert join_chunks(chunks, ["Fin du paragraphe.", "Nouveau paragraphe."]) == "Fin du paragraphe.\n\nNouveau paragraphe."
    chunks = ["Une phrase. ", "Une autre."]
    assert join_chunks(chunks, ["Une phrase.", "Une autre."]) == "Une phrase. Une autre."


# --- Contrôles de continuité ------------------------------------------------------------------------

CHUNKS = [
    "Nous lisons en la parabole qu'un Samaritain eut compassion. Il reserra ses playes avec du vin. ",
    "C'est là le vray emblême de Iesus Christ et de son Evangile qui guerit les ames navrées. ",
]


def test_junction_clean():
    answers = [
        "Nous lisons en la parabole qu'un Samaritain eut compassion. Il resserra ses plaies avec du vin.",
        "C'est là le vrai emblème de Jésus-Christ et de son Évangile qui guérit les âmes navrées.",
    ]
    assert check_junctions(CHUNKS, answers) == []


def test_junction_detects_duplicate():
    answers = ["… ses plaies avec du vin.", "Avec du vin. C'est là le vrai emblème de Jésus-Christ."]
    assert "doublon" in kinds(check_junctions(CHUNKS, answers))


def test_junction_detects_truncated_sentence():
    answers = ["Nous lisons en la parabole qu'un Samaritain eut compassion. Il resserra ses", "C'est là le vrai emblème."]
    assert "phrase_tronquee" in kinds(check_junctions(CHUNKS, answers))


def test_junction_detects_added_period():
    chunks = ["Il reserra ses playes avec du vin et\n", "de l'huile pour les adoucir."]
    answers = ["Il resserra ses plaies avec du vin et.", "de l'huile pour les adoucir."]
    assert "point_ajoute" in kinds(check_junctions(chunks, answers))


def test_junction_detects_copied_next_context():
    answers = [
        "Nous lisons en la parabole qu'un Samaritain eut compassion. Il resserra ses plaies avec du vin. "
        "C'est là le vrai emblème de Jésus-Christ et de son Évangile.",
        "C'est là le vrai emblème de Jésus-Christ et de son Évangile qui guérit les âmes navrées.",
    ]
    found = kinds(check_junctions(CHUNKS, answers))
    assert "suite_recopiee" in found or "doublon" in found, found


def test_junction_detects_copied_previous_context():
    answers = [
        "Nous lisons en la parabole qu'un Samaritain eut compassion.",
        "Il resserra ses plaies avec du vin. C'est là le vrai emblème de Jésus-Christ et de son Évangile.",
    ]
    assert "contexte_recopie" in kinds(check_junctions(CHUNKS, answers))


# --- Contrôles par morceau et texte final -----------------------------------------------------------

def test_chunk_detects_omission_and_additions():
    source = SENTENCE * 3 + "Mais auffi n'eftoit-ce pas en ce fens qu'il le confideroit. " * 4
    good = (SENTENCE * 3 + "Mais aussi n'était-ce pas en ce sens qu'il le considérait. " * 4)
    assert check_chunk(source, good)["missing"] == []
    bad = SENTENCE * 3 + " [1 Cor. 9:19]"
    r = check_chunk(source, bad)
    assert r["missing"] and r["added"] == ["[1 Cor. 9:19]"]


def test_failed_chunk_is_split_and_resent():
    import re
    import ocr_text_to_modernized_text as m

    sent = []

    def fake_run_prompts(site, prompts, timeout_s=300, document="", allow_partial=False):
        sent.extend(prompts)  # faux LLM : renvoie le TEXTE À RÉÉCRIRE tel quel
        return [re.search(r"\[TEXTE À RÉÉCRIRE\]\n(.*?)\n\[FIN DU TEXTE À RÉÉCRIRE\]", p, re.S).group(1) for p in prompts]

    original, m.run_prompts = m.run_prompts, fake_run_prompts
    original_log, m.write_log = m.write_log, lambda message: None
    try:
        chunks = ["Premier morceau. ", SENTENCE * 20, "Dernier morceau."]
        parts = m.fill_failed_chunks("doc", "gemini", "CONSIGNES", chunks, ["Premier morceau.", None, "Dernier morceau."], 300)
    finally:
        m.run_prompts, m.write_log = original, original_log
    assert len(sent) == 2  # le morceau refusé est renvoyé en deux moitiés
    assert all("[CONTEXTE PRÉCÉDENT" in p and "[SUITE" in p for p in sent)
    assert parts[1].split() == chunks[1].split()  # les deux moitiés recollées redonnent tout le morceau


def test_extract_answer_drops_interface_labels():
    from browser_llm import extract_answer

    raw = "Extrait de code\n\nVoici maintenant quel sera votre sort.\n###FIN###"
    assert extract_answer(raw) == "Voici maintenant quel sera votre sort."
    assert extract_answer("```text\nUn texte.\n```\n###FIN###") == "Un texte."


def test_residual_archaic():
    assert residual_archaic("Il estoit jusques à moy, et il croit qu'il doit.") == {"estoit": 1, "jusques": 1, "moy": 1}


if __name__ == "__main__":
    tests = [(name, f) for name, f in sorted(globals().items()) if name.startswith("test_")]
    failed = 0
    for name, f in tests:
        try:
            f()
            print(f"OK    {name}")
        except AssertionError as exc:
            failed += 1
            print(f"ÉCHEC {name} : {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} tests réussis")
    raise SystemExit(1 if failed else 0)
