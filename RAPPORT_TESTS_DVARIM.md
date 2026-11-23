# Rapport de tests : 19 prédications de dvarim.fr (24 octobre 2026)

## Objectif

Vérifier la pipeline complète (PDF → PNG → OCR → modernisation par Gemini dans le navigateur → Word → PDF → Markdown) sur des textes réels de longueur moyenne. On contrôle en priorité :

- **la continuité entre morceaux** : une phrase ne doit pas être coupée, doublée ou tronquée à la frontière entre deux prompts ;
- la fidélité au texte (pas d'omission, pas d'ajout) ;
- la modernisation de l'orthographe.

## Échantillon

- **19 PDF de 15 auteurs**, du XVIIe siècle (Du Moulin, Morus, Le Faucheur, Durant, Fléchier, Jaquelot…) au XIXe siècle (A. Monod, Bersier, Cellérier, Scholl…).
- Tirés au hasard (graine fixe) dans `H:\Mon Drive\Ressources chrétiennes\predications\dvarim.fr`, entre 14 et 30 pages, **432 pages au total**.
- Copiés dans `tests_dvarim/`, un dossier ignoré par Git qui contient aussi toutes les sorties.

## Méthode

- Lot exécuté par `python run_batch.py tests_dvarim`, avec les mêmes étapes que l'application Streamlit et Gemini en mode invité (sans compte).
- Logs de l'exécution : `logs/run_20261024_153011.log`, puis les reprises `run_20261024_182731.log` et `run_20261024_205245.log`.
- Contrôles automatiques (`quality_checks.py`), journalisés pour chaque document :
  - pour chaque morceau : mots de l'OCR retrouvés, passages omis (≥ 20 mots, hors bruit d'OCR et passages déplacés), crochets ajoutés ;
  - pour chaque jointure : mots répétés de part et d'autre, phrase tronquée, point ajouté au milieu d'une phrase, contexte (CONTEXTE PRÉCÉDENT ou SUITE) recopié ;
  - sur le texte final : s long, graphies anciennes restantes.
- Un morceau fautif est **renvoyé automatiquement** à Gemini, avec le problème constaté, et la meilleure réponse est gardée.
- J'ai recalculé les contrôles sur les textes finaux pour ce rapport.
- Relecture humaine (par moi) d'extraits OCR / texte modernisé de 4 auteurs : Du Moulin, Morus, Fléchier, Bersier.

## Résultats globaux

| Indicateur | Résultat |
|---|---|
| Documents traités de bout en bout (Word, PDF et Markdown générés) | **19 / 19** |
| Morceaux envoyés | 124 (4 à 11 par document) |
| Prompts envoyés au total (nouveaux essais et renvois compris) | 155 |
| **Jointures entre morceaux contrôlées** | **105** |
| Jointures signalées | 5, **toutes résolues** (3 corrigées au recollage, 2 renvoyées au LLM puis contrôlées sans problème) |
| **Problèmes de continuité restants** | **0** |
| Omissions signalées puis renvoyées au LLM | 9 morceaux dans 5 documents (AMonod, Chatelain, DuMoulin_S_50, Durant, Nardin). Une partie étaient du bruit d'OCR signalé à tort, avant l'ajout du filtre : au moins 2 dans DuMoulin_S_50. |
| Omissions restantes (≥ 20 mots) | **0** |
| Crochets ou notes ajoutés | 0 |
| s long « ſ » | 0 |
| Graphies anciennes restantes | 21 au total (« pource » ×16, « jusques » ×2, « avoit », « miroit », « encensoit ») |
| Durée moyenne par document | environ 10 minutes, 3 h 27 de traitement au total |

## Détail par document

| Document | Pages | Morceaux | Prompts envoyés | Échecs (passages) | Renvois qualité | Jointures signalées | Omissions finales | Ajouts | Graphies anciennes restantes |
|---|---|---|---|---|---|---|---|---|---|
| AMonod_S_19_Herode | 23 | 6 | 7 | 0 | 1 | 0 | 0 | 0 | 0 |
| Babut_S_16_Jour-salut | 25 | 6 | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| Bersier_S_70_Douleur | 24 | 6 | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| Cellerier_S_36_Presence | 26 | 7 | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| Chatelain_S_50_Insulte | 28 | 7 | 9 | 0 | 1 | 0 | 0 | 0 | 0 |
| DuMoulin_S_15_1Pierre | 26 | 8 | 9 | 1 | 0 | 1 | 0 | 0 | 0 |
| DuMoulin_S_50_Apocalypse | 24 | 7 | 11 | 0 | 1 | 0 | 0 | 0 | 6 (pource ×6) |
| Durant_S_25_Tentation-16 | 30 | 8 | 11 | 0 | 1 | 0 | 0 | 0 | 9 (pource ×8, jusques ×1) |
| Flechier_S_17_Envie | 14 | 7 | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| HMonodP_S_41_Crainte | 22 | 7 | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| Jaquelot_S_29_Messie | 16 | 4 | 7 | 1 | 0 | 0 | 0 | 0 | 0 |
| Jaquelot_S_38_Triomphe | 17 | 4 | 8 | 1 | 1 | 1 | 0 | 0 | 0 |
| LeFaucheur_S_24_Ps-2 | 22 | 5 | 5 | 1 | 0 | 0 | 0 | 0 | 2 (avoit ×1, pource ×1) |
| LeFaucheur_S_68_Ps-16-8-11 | 29 | 7 | 7 | 2 | 0 | 1 | 0 | 0 | 2 (jusques ×1, pource ×1) |
| Morus_S_20_Philippiens-I | 23 | 6 | 6 | 1 | 0 | 0 | 0 | 0 | 0 |
| Morus_S_95_2Corinthiens-XII-2 | 27 | 7 | 7 | 2 | 0 | 0 | 0 | 0 | 2 (miroit ×1, encensoit ×1) |
| Nardin_S_46_Trinite8 | 17 | 11 | 18 | 2 | 1 | 1 | 0 | 0 | 0 |
| Reguis_S_43_Service | 24 | 6 | 6 | 0 | 0 | 1 | 0 | 0 | 0 |
| Scholl_S_13_Necessite-Esprit | 15 | 5 | 7 | 1 | 0 | 0 | 0 | 0 | 0 |

« Échecs (passages) » compte les passages du lot où le document a échoué avant de réussir (réseau, blocage, refus ; voir Incidents). « Prompts envoyés » additionne tous les passages ; un passage bloqué n'a pas pu compter ses prompts.

## Continuité entre morceaux (problème prioritaire)

Les 5 jointures signalées, et le texte final correspondant :

| Document | Problème détecté | Résolution | Texte final |
|---|---|---|---|
| Reguis_S_43 | point ajouté au milieu d'une phrase (« …à des. » / « jeûnes… ») | recollage | « …à des abstinences et à des jeûnes mille fois plus sévères… » |
| DuMoulin_S_15 | mot répété (« …à imiter. » / « imiter. Elle… ») | recollage | « …plusieurs exemples à imiter. Elle nous propose… » |
| LeFaucheur_S_68 | point ajouté au milieu d'une phrase (« …celle des. » / « autres hommes… ») | recollage | « …comme celle des autres hommes se pourrit dans leur tombeau. » |
| Jaquelot_S_38 | contexte SUITE recopié en fin de morceau 1 | renvoi au LLM | contrôle après renvoi sans problème |
| Nardin_S_46 | phrase tronquée en fin de morceau 6 | renvoi au LLM | contrôle après renvoi : 10 jointures, aucun problème |

**La preuve jointure par jointure (105 jointures, extrait de l'OCR et du texte final pour chacune) est dans [PREUVE_CONTINUITE.md](PREUVE_CONTINUITE.md).** En la construisant, j'ai trouvé une jointure fautive que les contrôles avaient manquée : Nardin 1/2, où la note de marge « Prop. » avait été prise pour une fin de phrase. Je l'ai corrigée dans la découpe, puis Nardin a été retraité ; ses chiffres dans le tableau ci-dessus sont ceux de la première exécution.

La découpe coupe en fin de phrase. Sur ces 19 OCR, la quasi-totalité des coupures tombent en fin de phrase ; les autres sont couvertes par le contexte joint à chaque prompt et par les contrôles ci-dessus. La logique de découpe et de recollage est couverte par 17 tests hors ligne : `python test_quality_checks.py`.

## Qualité lue sur extraits

- **Textes du XVIIe siècle** : l'orthographe est modernisée et les erreurs d'OCR sont corrigées, sans changer le texte. Exemples :
  - Du Moulin : « cftre portee en fon lieu » → « être portée en son lieu », « prine-‘tion de l’E(prit » → « privation de l'Esprit », « ñ Dieu » → « si Dieu » ;
  - Morus : « enfloit fi forte courage » → « enflait si fort le courage », « cout pud » → « tout nu », « fourcilque » → « sourcil que ».
- Les en-têtes de page (« O 4 216 - V. Decape ») sont retirés.
- **Textes du XIXe siècle** (Bersier) : le texte reste quasi identique, et seules les césures sont recollées. Petit écart : « un Être vivant » devient « un être vivant ».
- Fléchier garde une espace avant la virgule (« Car , MESSIEURS ») : la ponctuation n'est pas toujours harmonisée.

## Incidents rencontrés pendant le lot et corrections apportées

| Incident | Effet | Correction |
|---|---|---|
| Coupure réseau de 17 h 40 à 18 h 08 (`ERR_SOCKET_NOT_CONNECTED`) | 8 documents en échec | nouveaux essais plus patients (3 essais, attentes de 10 puis 30 s) ; reprise du lot qui réutilise l'OCR déjà fait |
| Sous-processus navigateur figé plus d'une heure (Morus_S_95) | lot bloqué | durée maximale pour le sous-processus et délai de 60 s sur toutes les actions Playwright ; le processus figé a été arrêté à la main |
| Refus de Gemini (« Je ne peux pas vous aider à ce sujet… ») sur des passages ordinaires (Scholl, Nardin) | attente inutile de 300 s, puis document en échec | refus détecté en 20 s avec nouvel essai dans une nouvelle conversation ; un morceau toujours refusé est redécoupé en deux et renvoyé, sans faire échouer les autres |
| Faux signalements d'omission : bruit d'OCR (ornements), passages déplacés, mots modernes en -oit | renvois inutiles | filtres ajoutés dans `quality_checks.py` ; la vraie omission de Daille_S_34 reste détectée |

Après ces corrections, les 19 documents ont réussi.

## Limites

- Les contrôles mesurent des écarts avec l'OCR, pas le sens : une omission de moins de 20 mots ou un contresens n'est pas détecté. La relecture humaine n'a porté que sur des extraits.
- « pource que » reste souvent tel quel (16 fois), malgré l'exemple dans le prompt.
- Gemini en mode invité peut refuser ou limiter l'accès sans prévenir. ChatGPT n'a pas été testé.
- Une erreur de lecture de l'OCR qui forme un vrai mot (« fais » pour « ſuis ») ne peut pas être corrigée par la modernisation.

## Reproduire

```bash
python run_batch.py tests_dvarim
python test_quality_checks.py
```

Relancer `run_batch.py` sur le même dossier saute les documents déjà modernisés et reprend les documents en échec.
