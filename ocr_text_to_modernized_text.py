
from browser_llm import (
    END_MARKER, SITES, BrowserLLMUnavailable, current_log, join_chunks, run_prompts, split_in_chunks, write_log,
)
import api_llm
import progress
from quality_checks import AUTO_FIXED, check_chunk, check_junctions, residual_archaic
from recette_data import RecetteData
import os

CHUNK_MAX_CHARS = 6000  # taille maximale d'un morceau envoyé au LLM (caractères du texte OCR)


def check_if_already_modernized(document_name, directory='.'):
    """
    Vérifie si le texte modernisé existe déjà pour un document donné.
    """
    # Retirer l'extension .txt si présente
    base_name = os.path.splitext(document_name)[0]

    # Construire le nom du fichier modernisé attendu
    if("_modernized_cleaned_text" not in document_name):
        document_name = f"{base_name}_modernized_cleaned_text.txt"

    # Construire le chemin absolu complet
    full_path = os.path.abspath(os.path.join(directory, document_name))

    # Debug utile
    print(f"Répertoire courant réel : {os.getcwd()}")
    print(f"Recherche du fichier : {full_path}")
    # print(f"Fichiers présents dans {os.path.abspath(directory)} : {os.listdir(os.path.abspath(directory))}")

    # Vérification d'existence
    return os.path.exists(full_path)

def build_chunk_prompt(task, chunks, i, context_chars=400):
    """Prompt du morceau ``i`` : consignes, fin du morceau précédent et début du suivant comme contexte.

    Le contexte permet au LLM de comprendre une phrase coupée entre deux morceaux sans la réécrire deux fois.
    """
    prompt = task
    if i > 0:
        before = chunks[i - 1][-context_chars:]
        before = before[before.find(" ") + 1:] if " " in before else before  # pas de mot tronqué
        prompt += f"\n[CONTEXTE PRÉCÉDENT — ne pas réécrire]\n{before.strip()}\n[FIN DU CONTEXTE PRÉCÉDENT]\n"
    prompt += f"\n[TEXTE À RÉÉCRIRE]\n{chunks[i].strip()}\n[FIN DU TEXTE À RÉÉCRIRE]\n"
    if i + 1 < len(chunks):
        after = chunks[i + 1][:context_chars]
        after = after[:after.rfind(" ")] if " " in after else after
        prompt += f"\n[SUITE — ne pas réécrire]\n{after.strip()}\n[FIN DE LA SUITE]\n"
    return prompt


def _chunk_problems(chunks, parts):
    """Problèmes par morceau (omissions, ajouts) et de jointure, indexés par morceau à renvoyer."""
    problems = {}
    for i, (chunk, part) in enumerate(zip(chunks, parts)):
        r = check_chunk(chunk, part)
        notes = [f"ta réponse a omis ce passage, qui doit y figurer : « {m[:1200]} »" for m in r["missing"]]
        if r["added"]:
            notes.append(f"ta réponse a ajouté des crochets absents du texte ({', '.join(r['added'][:3])}) : n'en ajoute pas")
        if notes:
            problems.setdefault(i, []).extend(notes)
    junctions = check_junctions(chunks, parts)
    for issue in junctions:
        if issue["kind"] not in AUTO_FIXED:
            problems.setdefault(issue["chunk"], []).append(issue["message"])
    return problems, junctions


def fill_failed_chunks(document_name, site, task, chunks, parts, timeout_s, record=None):
    """Morceaux sans réponse (refus du modèle, échec) : redécoupés en deux moitiés et renvoyés, un texte
    plus court passant souvent le filtre. Lève BrowserLLMUnavailable si une moitié échoue encore."""
    parts = list(parts)
    for i in [k for k, p in enumerate(parts) if p is None]:
        halves = split_in_chunks(chunks[i], max_chars=len(chunks[i]) // 2 + 200)
        # Contexte : le morceau précédent et le suivant encadrent les moitiés
        local = ([chunks[i - 1]] if i > 0 else []) + halves + ([chunks[i + 1]] if i + 1 < len(chunks) else [])
        first = 1 if i > 0 else 0
        prompts = [build_chunk_prompt(task, local, first + k) for k in range(len(halves))]
        write_log(f"document={document_name} | morceau {i + 1} sans réponse : renvoi en {len(halves)} parties")
        answers = run_prompts(site, prompts, timeout_s, document=f"{document_name} (morceau {i + 1} redécoupé)")
        parts[i] = join_chunks(halves, answers)
        if record is not None:
            record.attempt(i, "redécoupe après refus", "\n\n===== MOITIÉ SUIVANTE =====\n\n".join(prompts),
                           parts[i], motif="aucune réponse au premier envoi (refus ou échec)", garde=True)
    return parts


def _score(chunk, part):
    """Plus petit = meilleur : mots de l'OCR manquants, crochets ajoutés."""
    r = check_chunk(chunk, part)
    return sum(len(m.split()) for m in r["missing"]) + 20 * len(r["added"])


def check_and_retry(document_name, site, task, chunks, parts, timeout_s, max_rounds=1, record=None):
    """Contrôle chaque morceau et chaque jointure ; renvoie au LLM les morceaux fautifs (avec le problème
    constaté) et garde la meilleure réponse. Tout est consigné dans le log de l'exécution (logs/)."""
    parts = list(parts)
    for round_ in range(max_rounds + 1):
        problems, junctions = _chunk_problems(chunks, parts)
        for i in range(len(chunks)):
            r = check_chunk(chunks[i], parts[i])
            write_log(
                f"document={document_name} | contrôle{' après renvoi' if round_ else ''} | morceau {i + 1}/{len(chunks)} "
                f"| mots OCR retrouvés={r['coverage']:.0%} | omissions={len(r['missing'])} | ajouts={len(r['added'])}"
            )
        for issue in junctions:
            fixed = "corrigé au recollage" if issue["kind"] in AUTO_FIXED else "à corriger"
            write_log(f"document={document_name} | continuité | {issue['message']} | {fixed}")
        if not junctions:
            write_log(f"document={document_name} | continuité | {len(chunks) - 1} jointure(s) contrôlée(s), aucun problème")
        if not problems or round_ == max_rounds:
            break
        redo = sorted(problems)
        extra = [
            build_chunk_prompt(task, chunks, i)
            + "\nATTENTION, une version précédente de ta réponse contenait ces erreurs, corrige-les :\n- "
            + "\n- ".join(problems[i])
            for i in redo
        ]
        try:
            answers = run_prompts(site, extra, timeout_s, document=f"{document_name} (renvoi des morceaux "
                                  f"{', '.join(str(i + 1) for i in redo)})", allow_partial=True)
        except BrowserLLMUnavailable as exc:
            write_log(f"document={document_name} | renvoi impossible : {exc}")
            break
        for i, prompt, answer in zip(redo, extra, answers):
            better = answer is not None and _score(chunks[i], answer) <= _score(chunks[i], parts[i])
            if record is not None:
                record.attempt(i, "renvoi après contrôle qualité", prompt, answer, motif=problems[i], garde=better)
            if better:
                parts[i] = answer
    write_log(f"document={document_name} | bilan qualité | problèmes restants={sum(map(len, problems.values()))}")
    return parts


def log_final_quality(document_name, text):
    """Contrôles du texte final recollé : s long, graphies anciennes restantes."""
    archaic = residual_archaic(text)
    write_log(
        f"document={document_name} | texte final | s long={text.count('ſ')} | graphies anciennes restantes="
        f"{sum(archaic.values())} {dict(sorted(archaic.items(), key=lambda kv: -kv[1])[:10]) if archaic else ''}"
    )


def modernize_and_clean_ocr_text(document_name, site, language, timeout_s=300):
    """
    Nettoie et modernise le texte OCRisé d'un document en le soumettant, par morceaux, à un LLM en ligne
    (Gemini ou ChatGPT) piloté dans un navigateur (voir browser_llm.py), sans clé API.

    Paramètres :
    ------------
    document_name : str
        Nom du document (ex. 'Daille_S_133_Noel')
    site : str
        'gemini' ou 'gpt' (LLM piloté dans le navigateur, sans clé API) ou 'api:<modèle>' (API Gemini,
        clé requise, voir api_llm.py), par exemple 'api:gemini-2.5-flash'
    language : str
        Langue du document à moderniser (ex. 'français')

    Résultat :
    ----------
    Crée le fichier {document_name}_modernized_cleaned_text.txt et retourne le texte nettoyé.
    """
    document_name = os.path.splitext(os.path.basename(document_name))[0]
    if site not in SITES and not api_llm.is_api(site):
        raise ValueError(f"Site inconnu : {site} (choix : {', '.join(SITES)} ou api:<modèle>)")

    task = '''Tu es un éditeur spécialiste des textes anciens. Voici un extrait d'un livre ancien en {language}, issu d'une reconnaissance de texte (OCR) imparfaite. Réécris-le en ORTHOGRAPHE MODERNE.

Règles :
1. Orthographe : modernise l'orthographe de CHAQUE mot ancien, dans tout le texte, sans exception. Exemples en français : estoit → était, seroit → serait, avoient → avaient, je fay → je fais, j'ay → j'ai, moy → moi, toy → toi, cecy → ceci, sçay → sais, nostre → notre, estes → êtes, aumosne → aumône, mesme → même, recognoistre → reconnaître, playe → plaie, reprens → reprends, ayme → aime, die → dise, treuve → trouve, abbaissé → abaissé, adjouste → ajoute, jusques → jusque, pource que → pour ce que, long-temps → longtemps, & → et.
2. Le s long « ſ » et le « f » qui le remplace par erreur d'OCR s'écrivent « s » (Verf. → Vers., eft → est, fçay → sais). N'écris JAMAIS le caractère « ſ ».
3. Ne change ni le vocabulaire, ni la syntaxe, ni le sens : pas de reformulation, pas de synonyme, pas de phrase ajoutée ou retirée. Seule l'orthographe et les accents changent. Pour les verbes, modernise la terminaison mais garde le même temps, le même mode et la même personne (avoit → avait, estoient → étaient, penfiez → pensiez).
4. Corrige les erreurs évidentes de l'OCR (lettres mal lues, mots collés ou coupés). Pour un mot mal lu, choisis la lecture la plus proche des lettres de l'OCR qui soit cohérente avec la phrase (jefray, fçay → je sais ; jamais un autre verbe).
5. Recolle les mots coupés en fin de ligne (césures) et supprime les retours à la ligne inutiles ; garde un saut de ligne entre les paragraphes.
6. Supprime les en-têtes courants répétés en haut de page, les numéros de page, les signatures d'imprimeur et les réclames (mot isolé en bas de page qui répète le premier mot de la page suivante).
7. Ponctuation et espaces modernes ; accents modernes.
8. Avant de répondre, relis ton texte : il ne doit rester AUCUNE graphie ancienne (terminaisons -oit, -oient, -ois de l'imparfait ou du conditionnel, s muet ancien comme estoit, nostre, mesme, y final comme moy, cecy, celuy, j'ay).
9. L'extrait fait partie d'un texte plus long, découpé en morceaux. Il peut être entouré d'un CONTEXTE PRÉCÉDENT et d'une SUITE : ils servent seulement à comprendre les phrases coupées, ne les réécris pas. Réécris uniquement le TEXTE À RÉÉCRIRE, de son premier à son dernier mot : s'il commence au milieu d'une phrase, commence ta réponse au même mot (sans majuscule ajoutée) ; s'il finit au milieu d'une phrase, arrête-toi au même mot, sans ajouter de ponctuation.
10. N'omets AUCUN passage : chaque phrase du TEXTE À RÉÉCRIRE doit se retrouver dans ta réponse. Si l'OCR a mélangé l'ordre des lignes (notes en marge, colonnes, saut de page), remets-les dans l'ordre logique sans rien perdre.
11. N'ajoute RIEN : pas de crochets, pas de référence, de titre ni de note qui ne soient pas dans le texte. Les références bibliques isolées dans la marge (par exemple « 2 Cor. 11 ») peuvent être supprimées.

Format de réponse STRICT : uniquement le texte réécrit, sans explication ni commentaire, dans UN SEUL bloc de code, suivi d'une dernière ligne contenant exactement {end_marker}
'''
    task = task.replace("{language}", language).replace("{end_marker}", END_MARKER)

    with open(f"{document_name}_ocr_text.txt", "r", encoding="utf-8") as fichier:
        ocr_text = fichier.read()

    chunks = split_in_chunks(ocr_text, max_chars=CHUNK_MAX_CHARS)
    prompts = [build_chunk_prompt(task, chunks, i) for i in range(len(chunks))]

    # Sauvegarde des prompts
    with open(f"{document_name}_modernization_prompt.txt", 'w', encoding='utf-8') as f_prompt:
        f_prompt.write(("\n\n" + "=" * 40 + "\n\n").join(prompts))

    # Données de recette : tout ce qu'il faut pour vérifier le travail après coup (<document>_recette.json)
    record = RecetteData(document_name, site, language, task, chunks, ocr_text, max_chars=CHUNK_MAX_CHARS)
    progress.set_stage("llm")
    progress.report(0, len(prompts), f"{len(prompts)} morceau(x) à moderniser")
    parts = run_prompts(site, prompts, timeout_s, document=document_name, allow_partial=True)
    for i, (prompt, part) in enumerate(zip(prompts, parts)):
        record.attempt(i, "premier envoi", prompt, part, garde=part is not None)
    progress.set_stage("llm_fix")  # morceaux refusés ou fautifs renvoyés
    progress.report(0, 1, "contrôle qualité")
    parts = fill_failed_chunks(document_name, site, task, chunks, parts, timeout_s, record=record)
    parts = check_and_retry(document_name, site, task, chunks, parts, timeout_s, record=record)
    progress.report(1, 1, "contrôle qualité terminé")
    # Filet de sécurité : le s long ne doit jamais apparaître dans le texte modernisé (même longueur : les
    # positions des morceaux dans le texte final restent exactes)
    starts = []
    modernized_cleaned_text = join_chunks(chunks, parts, starts=starts).replace("ſ", "s")
    log_final_quality(document_name, modernized_cleaned_text)
    record.finish(chunks, parts, modernized_cleaned_text, starts, check_junctions(chunks, parts), log_path=current_log())
    print(f"Données de recette enregistrées : {record.save()}")

    # Écriture du texte nettoyé
    with open(f"{document_name}_modernized_cleaned_text.txt", 'w', encoding='utf-8') as f:
        f.write(modernized_cleaned_text)

    print(f"✅ Texte modernisé enregistré : {document_name}_modernized_cleaned_text.txt")
    return modernized_cleaned_text
