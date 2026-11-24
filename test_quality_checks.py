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


def test_chunk_omission_is_detected_even_if_the_text_repeats_later():
    # Le verset est cité deux fois dans l'original ; le LLM omet le début (titre + première citation) : le passage
    # omis ne doit pas être pris pour un passage « déplacé » sous prétexte que le verset réapparaît plus loin.
    verse = "N'ayez point de peur car voici je vous annonce une grande joie qui sera à tout le peuple. "
    title = "Sermon dix-neuvième pour le jour de Noël prononcé un mercredi vingt-cinq décembre mille six cent trente. "
    body = "Nous célébrâmes dimanche dernier la mort du Seigneur Jésus aujourd'hui nous solennisons sa naissance. " * 3
    source = title + verse + body + "Et l'ange leur dit encore : " + verse + body
    answer = body + "Et l'ange leur dit encore : " + verse + body
    assert check_chunk(source, answer)["missing"], "omission du début non détectée"


def test_chunk_moved_passage_is_not_an_omission():
    a = "Premier passage qui parle de la grâce et de la foi des fidèles assemblés dans le temple ce jour-là. " * 2
    b = "Second passage qui décrit la charité des Philippiens envers l'apôtre prisonnier à Rome sous Néron. " * 2
    c = "Troisième passage sur la joie de saint Paul qui se réjouit au Seigneur de leur soin pour lui. " * 2
    assert check_chunk(a + b + c, a + c + b)["missing"] == []


def test_extract_answer_drops_interface_labels():
    from browser_llm import extract_answer

    raw = "Extrait de code\n\nVoici maintenant quel sera votre sort.\n###FIN###"
    assert extract_answer(raw) == "Voici maintenant quel sera votre sort."
    assert extract_answer("```text\nUn texte.\n```\n###FIN###") == "Un texte."


# --- Mode API sans clé et échec du navigateur sans repli (aucun appel réseau, aucune clé) -----------------

class _NoKey:
    """Isole le test : pas de clé (ni variable d'environnement, ni vrai .env), log dans un fichier temporaire."""

    def __enter__(self):
        import os
        import tempfile
        from pathlib import Path

        import api_llm
        import browser_llm

        self.mods = (api_llm, browser_llm)
        self.saved = (browser_llm._run_log, browser_llm._run_total, api_llm._api_key, api_llm._fallback_model,
                      dict(os.environ), api_llm.ENV_FILE)
        self.tmp = tempfile.TemporaryDirectory()
        browser_llm._run_log, browser_llm._run_total = Path(self.tmp.name) / "run.log", 0
        api_llm.ENV_FILE = Path(self.tmp.name) / "absent.env"  # jamais le vrai .env de l'utilisateur
        for var in api_llm.KEY_VARS:
            os.environ.pop(var, None)
        api_llm.set_api_key(None)
        api_llm.set_fallback(None)
        return self

    def log(self):
        return self.mods[1]._run_log.read_text(encoding="utf-8")

    def __exit__(self, *exc):
        import os

        api_llm, browser_llm = self.mods
        (browser_llm._run_log, browser_llm._run_total, api_llm._api_key, api_llm._fallback_model,
         env, api_llm.ENV_FILE) = self.saved
        os.environ.clear()
        os.environ.update(env)
        self.tmp.cleanup()


def test_api_mode_without_key_explains_how_to_set_it():
    from browser_llm import BrowserLLMUnavailable, run_prompts

    with _NoKey() as ctx:
        try:
            run_prompts("api:gemini-2.5-flash", ["p1"], document="doc")
            raise AssertionError("une erreur était attendue")
        except BrowserLLMUnavailable as exc:
            assert "GEMINI_API_KEY" in str(exc)
        assert "prompts_envoyes=0" in ctx.log()  # rien n'a été envoyé


def test_browser_failure_without_fallback_still_raises():
    import browser_llm

    with _NoKey():
        original = browser_llm._run_browser
        browser_llm._run_browser = lambda site, prompts, timeout_s: {
            "answers": [None], "prompts_sent": 1, "error": "refus du modèle"}
        try:
            try:
                browser_llm.run_prompts("gemini", ["p1"], document="doc")
                raise AssertionError("une erreur était attendue")
            except browser_llm.BrowserLLMUnavailable:
                pass
        finally:
            browser_llm._run_browser = original


def test_stale_exports_are_regenerated():
    # Un Word (ou PDF, ou Markdown) plus ancien que sa source est refait : sinon il montre l'ancien texte.
    import os
    import tempfile

    from convert_modernized_txt_to_word import check_if_modernized_txt_already_exported_to_word as word_done
    from convert_modernized_word_to_pdf import check_if_modernized_txt_already_exported_to_pdf as pdf_done

    with tempfile.TemporaryDirectory() as tmp:
        def make(name, age):  # age en secondes avant maintenant
            path = os.path.join(tmp, name)
            open(path, "w").close()
            os.utime(path, (os.path.getmtime(path) - age,) * 2)

        make("Doc_modernized_cleaned_text.docx", 100)
        make("Doc_modernized_cleaned_text.txt", 0)  # texte relancé après l'export Word
        assert not word_done("Doc", tmp)
        make("Doc_modernized_cleaned_text.docx", 0)
        assert word_done("Doc", tmp)
        make("Doc_modernized_cleaned_text.pdf", 100)  # PDF plus ancien que le Word
        assert not pdf_done("Doc", tmp)
        make("Doc_modernized_cleaned_text.pdf", -10)
        assert pdf_done("Doc", tmp)


def test_recette_data_is_saved_with_exact_positions():
    # Modernisation complète avec un faux LLM (renvoie le texte tel quel) : le fichier de recette contient les
    # positions exactes de chaque morceau dans l'OCR et dans le texte final, et chaque envoi.
    import json
    import os
    import re
    import tempfile

    import ocr_text_to_modernized_text as m

    def fake_run_prompts(site, prompts, timeout_s=300, document="", allow_partial=False):
        return [re.search(r"\[TEXTE À RÉÉCRIRE\]\n(.*?)\n\[FIN DU TEXTE À RÉÉCRIRE\]", p, re.S).group(1) for p in prompts]

    ocr = (SENTENCE * 40 + "\n\n") * 4
    saved = (m.run_prompts, m.write_log, m.CHUNK_MAX_CHARS, os.getcwd())
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        m.run_prompts, m.write_log, m.CHUNK_MAX_CHARS = fake_run_prompts, lambda message: None, 1500
        try:
            open("Doc_ocr_text.txt", "w", encoding="utf-8").write(ocr)
            import contextlib
            import io

            with contextlib.redirect_stdout(io.StringIO()):  # affichages avec emoji : console cp1252 des tests
                final = m.modernize_and_clean_ocr_text("Doc", "gemini", "français")
            data = json.load(open("Doc_recette.json", encoding="utf-8"))
        finally:
            m.run_prompts, m.write_log, m.CHUNK_MAX_CHARS = saved[:3]
            os.chdir(saved[3])
    morceaux = data["morceaux"]
    assert len(morceaux) > 1 and data["taille_max_morceau"] == 1500
    assert "".join(ocr[x["ocr_debut"]:x["ocr_fin"]] for x in morceaux) == ocr
    for x in morceaux:
        assert final[x["final_debut"]:x["final_debut"] + len(x["reponse_finale"].strip())] == x["reponse_finale"].strip()
        assert x["envois"][0]["type"] == "premier envoi" and x["envoi_garde"] == 0
        assert "[TEXTE À RÉÉCRIRE]" in x["envois"][0]["prompt"]
    assert data["consignes"] and data["texte_final"]["caracteres"] == len(final)


def test_recette_llm_judges_cuts_and_writes_the_page():
    # Étape de recette avec un faux LLM : prompts par lots (texte seul en navigateur, texte + images en API),
    # verdicts JSON lus, fichier recette_<doc>.llm.json et page HTML écrits, vérification manuelle jamais écrasée.
    import contextlib
    import io
    import json
    import os
    import re
    import tempfile
    from pathlib import Path

    import ocr_text_to_modernized_text as m
    import recette_llm
    import recette_modernisation as R

    def fake_modernize(site, prompts, timeout_s=300, document="", allow_partial=False):
        return [re.search(r"\[TEXTE À RÉÉCRIRE\]\n(.*?)\n\[FIN DU TEXTE À RÉÉCRIRE\]", p, re.S).group(1) for p in prompts]

    sent = []

    def fake_judge(site, prompts, timeout_s=300, document="", allow_partial=False):
        sent.extend(prompts)
        out = []
        for p in prompts:
            text = p if isinstance(p, str) else " ".join(x for x in p if isinstance(x, str))
            ids = re.findall(r"\[(?:COUPURE|OMISSION POSSIBLE) ([co]\d+)", text)
            out.append("```json\n" + json.dumps([{"id": i, "verdict": "warn" if i == "c2" else "ok",
                                                   "explication": f"jugé {i}"} for i in ids]) + "\n```")
        return out

    ocr = "".join(f"Paragraphe {n}. " + SENTENCE * 25 + "\n\n" for n in range(6))
    saved = (m.run_prompts, m.write_log, m.CHUNK_MAX_CHARS, recette_llm.run_prompts, recette_llm.write_log,
             R.ROOT, os.getcwd())
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        m.run_prompts, m.write_log, m.CHUNK_MAX_CHARS = fake_modernize, lambda message: None, 1500
        recette_llm.run_prompts, recette_llm.write_log, R.ROOT = fake_judge, lambda message: None, Path(tmp)
        try:
            Path("Doc_ocr_text.txt").write_text(ocr, encoding="utf-8")
            Path("pages_textes/Doc").mkdir(parents=True)
            Path("pages_textes/Doc/page0001-1.txt").write_text(ocr[:-1], encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                m.modernize_and_clean_ocr_text("Doc", "gemini", "français")
                summary = recette_llm.run("Doc", "gemini")  # navigateur : texte seul
                n_cuts = summary["coupures"]
                assert all(isinstance(p, str) for p in sent) and len(sent) == -(-summary["elements"] // 10)
                llm_notes = json.loads(Path("recette_Doc.llm.json").read_text(encoding="utf-8"))
                assert llm_notes["_source"] == "llm" and llm_notes["2"] == ["warn", "jugé c2"]
                assert summary["juges"] == summary["elements"] and summary["warn"] == 1 and summary["ok"] == n_cuts - 1
                assert "Vérification par le LLM (gemini)" in Path("recette_Doc.html").read_text(encoding="utf-8")
                # Une vérification manuelle existante reste prioritaire et n'est pas écrasée
                Path("recette_Doc.notes.json").write_text(json.dumps({"1": ["err", "manuel"]}), encoding="utf-8")
                sent.clear()
                summary = recette_llm.run("Doc", "api:gemini-2.5-flash")  # API : liste texte (+ images si pages)
                assert all(isinstance(p, list) for p in sent)
                assert json.loads(Path("recette_Doc.notes.json").read_text(encoding="utf-8")) == {"1": ["err", "manuel"]}
                assert summary["err"] == 1 and "Vérification manuelle" in Path("recette_Doc.html").read_text(encoding="utf-8")
        finally:
            (m.run_prompts, m.write_log, m.CHUNK_MAX_CHARS, recette_llm.run_prompts, recette_llm.write_log,
             R.ROOT) = saved[:6]
            os.chdir(saved[6])
    # Lot sans réponse (réponse incomplète, constaté) : ses éléments sont rejugés par petits lots
    calls = []

    def flaky_judge(site, prompts, timeout_s=300, document="", allow_partial=False):
        calls.append(len(prompts))
        answers = fake_judge(site, prompts)
        return [None] + answers[1:] if len(calls) == 1 else answers

    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        m.run_prompts, m.write_log, m.CHUNK_MAX_CHARS = fake_modernize, lambda message: None, 600
        recette_llm.run_prompts, recette_llm.write_log, R.ROOT = flaky_judge, lambda message: None, Path(tmp)
        try:
            Path("Doc_ocr_text.txt").write_text(ocr, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                m.modernize_and_clean_ocr_text("Doc", "gemini", "français")
                summary = recette_llm.run("Doc", "gemini")
            assert summary["elements"] > 10 and summary["juges"] == summary["elements"] and len(calls) == 2
        finally:
            (m.run_prompts, m.write_log, m.CHUNK_MAX_CHARS, recette_llm.run_prompts, recette_llm.write_log,
             R.ROOT) = saved[:6]
            os.chdir(saved[6])
    assert recette_llm.parse_verdicts("pas de JSON", {"c1"}) == {}
    assert recette_llm.parse_verdicts('Voici :\n[{"id": "c1", "verdict": "err", "explication": "x"}, '
                                      '{"id": "c9", "verdict": "ok"}]', {"c1"}) == {"c1": ["err", "x"]}


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
