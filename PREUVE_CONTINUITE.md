# Preuve de continuité entre morceaux : 19 textes de dvarim.fr

Problème à éviter : *une même phrase séparée entre deux morceaux, son début à la fin d'un morceau et sa suite au début du suivant*, ce qui donne une phrase coupée, doublée ou mal raccordée dans le texte modernisé.

## Méthode

Pour **chaque jointure** entre deux morceaux, dans chacun des 19 textes :

1. **Coupure dans l'OCR** : la découpe (`split_in_chunks`) est recalculée à l'identique. On montre la fin du morceau, le repère ‖, puis le début du suivant, et on vérifie que la coupure suit une fin de phrase.
2. **Texte final à la jointure** : l'OCR et le texte modernisé sont alignés mot à mot. On montre le texte final de part et d'autre de l'endroit correspondant. Le repère ‖ est placé par cet alignement et peut être décalé de quelques mots.
3. **Contrôles automatiques sur le texte final** : aucun mot répété de part et d'autre de la jointure, aucun point suivi d'une minuscule (phrase coupée puis raccordée).
4. **Log de l'exécution** (`logs/`) : résultat des contrôles de continuité faits pendant le traitement, avant recollage.

Les jointures dont l'alignement est imprécis (plus de 3 mots entre les deux repères) ont été relues à la main ; le commentaire est dans la colonne « Contrôle ».

## Bilan

| Indicateur | Résultat |
|---|---|
| Textes | 19 |
| Jointures contrôlées | 105 |
| Coupures placées après une fin de phrase dans l'OCR | 105 / 105 |
| Mots répétés à la jointure dans le texte final | 0 |
| Point au milieu d'une phrase à la jointure | 0 |
| **Jointures continues (phrase ni coupée, ni doublée, ni tronquée)** | **105 / 105** |

## Défaut trouvé par cette preuve, puis corrigé

La première version de cette preuve a trouvé **une jointure fautive sur 105 : Nardin_S_46_Trinite8, jointure 1/2**. La note de marge « Prop. » (pour « Proposition »), suivie d'une ligne vide et d'une majuscule, avait été prise pour une fin de phrase. La phrase « Ainsi au lieu de vous faire ici le tableau du faux et du [vrai Chrétien, en examinant…] » était donc coupée entre les morceaux 1 et 2. Le texte final donnait : « …le tableau du faux et du Unsuau 3 Prop. E@ ¦ Prop. Prop. Du faux et du vrai Chrétien… ».

Correction : les titres de notes en marge (Prop., Exord., Appl.…) ne comptent plus comme fins de phrase (`_ABBREVIATIONS`, browser_llm.py). Seul Nardin a été retraité, en réutilisant son OCR. Le morceau 1 se termine maintenant après « …les espérances qu'ils se font du salut. », et le texte final donne : « Ainsi au lieu de vous faire ici le tableau du faux et du vray Chrétien, en examinant : I. Les caractères du faux Chrétien, II. Ceux du vray. » Les tableaux ci-dessous montrent l'état après correction. L'ancienne sortie de Nardin est conservée hors du projet pour comparaison.

## AMonod_S_19_Herode : 6 morceaux, 5 jointures

Log de l'exécution (contrôle de continuité) : `5 jointure(s) contrôlée(s), aucun problème`

| Jointure | Coupure dans l'OCR (fin ‖ début) | Texte final à la jointure | Contrôle |
|---|---|---|---|
| 1/2 | …ment fameux par leurs entre- prises contre le Seigneur et contre son règne. **‖** H y a eu quatre Hérodes. Le premier, Hérode-le-Grand*, fit mas- 1 2 Thess. … | devenu tristement fameux par leurs entreprises contre le Seigneur et contre son règne. Il ‖ y a eu quatre Hérodes. Le premier, Hérode le Grand*, fit massacrer les | ✅ continu |
| 2/3 | …uisse se faire jour jusqu’à eux. Et qui sait si Hérode ne l'écoutera point? **‖** La conversion dépend-elle de nos calculs? et Dieu ne peut-il pas donner à d… | jour jusqu’à eux. Et qui sait si Hérode ne l'écoutera point? 1 Luc II, 19, — Matth. XVI, 23. ‖ La conversion dépend-elle de nos calculs ? et Dieu ne peut-il pas | ✅ continu, relu à la main : la phrase « …ne l'écoutera point? » se termine, « La conversion dépend-elle… » commence. Entre les deux, la note de bas de page de l'original (« 1 Luc II, 19, — Matth. XVI, 23. ») est conservée. |
| 3/4 | … dans le livre qu’à cause de la fidélité avec laquelle il peint notre cœur. **‖** Hérode retient Jean-Baptiste en prison et interrompt le cours de son minist… | livre qu’à cause de la fidélité avec laquelle il peint notre cœur. ‖ Hérode retient Jean-Baptiste en prison et interrompt le cours de son ministère | ✅ continu |
| 4/5 | …uissance de la parole de Dieu! O liberté sainte de ses serviteurs opprimés! **‖** Que si la captivité de Jean-Baptiste lui fournit de nouvelles occasions de … | puissance de la parole de Dieu ! O liberté sainte de ses serviteurs opprimés ! ‖ Que si la captivité de Jean-Baptiste lui fournit de nouvelles occasions de | ✅ continu |
| 5/6 | …nè- “ «rent avec Christ les mille ans ; c’est la première ré- « surrection. **‖** Bienheureux et saint celui qui a part à la « première résurrection * ! » O … | ils vécurent et régnèrent avec Christ les mille ans ; c’est la première résurrection. ‖ Bienheureux et saint celui qui a part à la « première résurrection ! » Ô mes | ✅ continu |

## Babut_S_16_Jour-salut : 6 morceaux, 5 jointures

Log de l'exécution (contrôle de continuité) : `5 jointure(s) contrôlée(s), aucun problème`

| Jointure | Coupure dans l'OCR (fin ‖ début) | Texte final à la jointure | Contrôle |
|---|---|---|---|
| 1/2 | …esponde à un besoin réel de l’homme, ni qu’il désigne un don réel’ de Dieu. **‖** Mes frères, on ne peut pas tout prouver. On ne le peut pas d’une manière ab… | réel de l’homme, ni qu’il désigne un don réel de Dieu. ‖ Mes frères, on ne peut pas tout prouver. On ne le peut pas | ✅ continu |
| 2/3 | …e, qu’il se hâte de fuir vers la lumière, car ce jour est le jour du salut. **‖** IL Si beaucoup pensent qu’il n’y a point de jour du salut, d’autres — et il… | de fuir vers la lumière, car ce jour est le jour du salut. II ‖ Si beaucoup pensent qu’il n’y a point de jour du salut | ✅ continu |
| 3/4 | …’est-il pas évident que c'est vous éloigner et non vous approcher du salut? **‖** Mais osons rechercher qui a raison, de Dieu ou de vous. Je rappelle que le … | pas évident que c'est vous éloigner et non vous approcher du salut? ‖ Mais osons rechercher qui a raison, de Dieu ou de vous. Je rappelle | ✅ continu |
| 4/5 | …sieurs) paraissaient fort malheureux. Il voulut sortir, quelqu’un l’arrêta. **‖** Sur ses ins- tances, le sévère gardien finit pourtant par le laisser passer… | en reconnut plusieurs) paraissaient fort malheureux. Il voulut sortir, quelqu’un l’arrêta. ‖ Sur ses instances, le sévère gardien finit pourtant par le laisser passer, mais | ✅ continu |
| 5/6 | …issant pour sauver sans retard ce qui nous en reste en le don- nant à Dieu. **‖** Mais est-ce possible? — Oui, par la puissance de Dieu qui agit en nous. S’i… | sauver sans retard ce qui nous en reste en le donnant à Dieu. ‖ Mais est-ce possible? — Oui, par la puissance de Dieu qui agit en | ✅ continu |

## Bersier_S_70_Douleur : 6 morceaux, 5 jointures

Log de l'exécution (contrôle de continuité) : `5 jointure(s) contrôlée(s), aucun problème`

| Jointure | Coupure dans l'OCR (fin ‖ début) | Texte final à la jointure | Contrôle |
|---|---|---|---|
| 1/2 | …rir; aucun de nous n’est oublié sur la liste des prédestinés de la douleur. **‖** Eh bien! voici un fait étrange : cette question de la souffrance, la plus u… | de nous n’est oublié sur la liste des prédestinés de la douleur. ‖ Eh bien! voici un fait étrange : cette question de la souffrance, la plus | ✅ continu |
| 2/3 | …stion que notre intelligence naturelle est absolument incapable d’éclairer. **‖** L’Écriture ne traite point le problème de la douleur d’une manière systémat… | projette sur cette question que notre intelligence naturelle est absolument incapable d’éclairer. ‖ L’Écriture ne traite point le problème de la douleur d’une manière | ✅ continu |
| 3/4 | …nsion du cœur, éveil de l’espérance éternelle. 42 LES EFFETS DE LA DOULEUR. **‖** Essayons de voir comment ces vertus croissent et mûrissent sous l’action de… | religieuse, éducation de la conscience, expansion du cœur, éveil de l’espérance éternelle. ‖ Essayons de voir comment ces vertus croissent et mûrissent sous l’action de | ✅ continu |
| 4/5 | …UR. 2° Elle fait plus, elle agit sur la conscience, elle dompte la volonté. **‖** Connaître la vérité ne suffit pas. On peut voir Dieu et mourir. Il y a loin… | Dieu. 2° Elle fait plus, elle agit sur la conscience, elle dompte la volonté. ‖ Connaître la vérité ne suffit pas. On peut voir Dieu et mourir. Il | ✅ continu |
| 5/6 | …es trouver si nombreux, on se re- proche de les avoir si longtemps ignorés. **‖** C’est de cette expérience que sort la sympathie, cette chose divine qui sig… | les trouver si nombreux, on se reproche de les avoir si longtemps ignorés. ‖ C’est de cette expérience que sort la sympathie, cette chose divine qui | ✅ continu |

## Cellerier_S_36_Presence : 7 morceaux, 6 jointures

Log de l'exécution (contrôle de continuité) : `6 jointure(s) contrôlée(s), aucun problème`

| Jointure | Coupure dans l'OCR (fin ‖ début) | Texte final à la jointure | Contrôle |
|---|---|---|---|
| 1/2 | …ns chaque circonstance nous attacher à ré- gler nos actions sur sa vylonté. **‖** Ces idées sans doute.ne sont point étrangères à la question qui nous occupe… | décrets, et dans chaque circonstance nous attacher à régler nos actions sur sa volonté. ‖ Ces idées sans doute ne sont point étrangères à la question qui nous | ✅ continu |
| 2/3 | …- ment de l’homme, tenoit essentiellement à l’ob- servation de ce précepte. **‖** Et comment cela ? Par les clartés que la pré- sence de Dieu, répand dans no… | le perfectionnement de l’homme, tenait essentiellement à l’observation de ce précepte. ‖ Et comment cela ? Par les clartés que la présence de Dieu répand dans | ✅ continu |
| 3/4 | …s aux perfections divines, de retracer en elle l’image auguste du Créateur. **‖** Vous le savez, chrétiens , il y a dans notre na- ture morale une loi puissa… | analogues aux perfections divines, de retracer en elle l’image auguste du Créateur. ‖ Vous le savez, chrétiens , il y a dans notre nature morale une loi | ✅ continu |
| 4/5 | …tes ses pensées : une lu- mière divine l’éclaire et le calme en même temps. **‖** Ai-je besoin d’ajouter qu’il oublié ainsi toutes ses peines ? Ah! si dans n… | ses pensées : une lumière divine l’éclaire et le calme en même temps. ‖ Ai-je besoin d'ajouter qu'il oublie ainsi toutes ses peines ? Ah | ✅ continu |
| 5/6 | …gré nous s ‘effacer de notre âme si nous n’étions attentifs à l’y retracer. **‖** I] faut donc, M. C. F., que ce soit là le plus cher, le plus constant de no… | effacer de notre âme si nous n’étions attentifs à l’y retracer. Il ‖ faut donc, M. C. F., que ce soit là le plus cher, le | ✅ continu |
| 6/7 | …le soir. Qu’elle préside à toutes vos occupations et qu’elle les sanctifie. **‖** Qui que vous soyez, M. F., pensez, pensez à ce Dieu qui n’est jamais loir d… | soir. Qu’elle préside à toutes vos occupations et qu’elle les sanctifie. ‖ Qui que vous soyez, M. F., pensez, pensez à ce Dieu qui n | ✅ continu |

## Chatelain_S_50_Insulte : 7 morceaux, 6 jointures

Log de l'exécution (contrôle de continuité) : `6 jointure(s) contrôlée(s), aucun problème`

| Jointure | Coupure dans l'OCR (fin ‖ début) | Texte final à la jointure | Contrôle |
|---|---|---|---|
| 1/2 | …ion, le gefte à l’outrage, ils lui difent des outrages en branlant la téte. **‖** Il eft rare que l’on en vienne à cet excès contre des malheureux , lorfqu’i… | geste à l'outrage, ils lui disent des outrages en branlant la tête. ‖ Il est rare que l'on en vienne à cet excès contre des | ✅ continu |
| 2/3 | …imés plus que fa propre vie, qu’il doit la don- ner pour le falut du Monde. **‖** Si Jéfus- Chrift fût defcendu de la croix, cotame ces infenfés le demandoie… | sa propre vie, qu'il doit la donner pour le salut du Monde. ‖ Si Jésus-Christ fût descendu de la croix, comme ces insensés le demandaient | ✅ continu |
| 3/4 | … que l’on auroit peine à croire, {fi l’on n’en avoit pas d’autres exemples. **‖** Un Hiftorien (*), qui n’eft nullement fuf ¦ (*) Le P. Daniel Hit. de France… | peine à croire, si l’on n’en avait pas d’autres exemples. ‖ Un Historien (*), qui n’est nullement sus ¦ (*) Le P. Daniel Hist. de France | ✅ continu |
| 4/5 | …ues au bout l’infame complot qu’ils avoient prémédité contre Jéfus- Chrift. **‖** Que f- roient-ils devenus li Jéfus- Chrift fût def- cendu de la croix , & q… | jusque au bout l’infâme complot qu’ils avaient prémédité contre Jésus-Christ. ‖ Que seraient-ils devenus si Jésus-Christ fût descendu de la croix, et | ✅ continu |
| 5/6 | …ver Es’ non point un bomme , Popprobre des bommes Es? le méprifé du Peuple. **‖** Tous ceux qui me'voyent fe mo- quent de moi ,îls me font la moue , ils bran… | non point un homme, l’opprobre des hommes et le méprisé du Peuple. ‖ Tous ceux qui me voient se moquent de moi, ils me font la | ✅ continu |
| 6/7 | …ecours de fes priè- res , pour émouvoir les entrailles de fon Père célefte. **‖** Chrétiens , cet exemple ne vous touche-t-il point ? Ne lirez-vous . H3 poin… | le secours de ses prières, pour émouvoir les entrailles de son Père céleste. ‖ Chrétiens , cet exemple ne vous touche-t-il point ? Ne lirez-vous point | ✅ continu |

## DuMoulin_S_15_1Pierre : 8 morceaux, 7 jointures

Log de l'exécution (contrôle de continuité) : `jointure 2/3 : 1 mot(s) répété(s) de part et d'autre (« …Écriture nous propose plusieurs exemples à imiter. » / « imiter. Elle nous propose la promptitude des Anges… ») ¦ corrigé au recollage`

| Jointure | Coupure dans l'OCR (fin ‖ début) | Texte final à la jointure | Contrôle |
|---|---|---|---|
| 1/2 | … ce tilcre d-S "inéteté pris en ce fens » ne peut conue- nir qu’a D'euieul. **‖** O: l'Eicriture difant que Dicueft (ain& nous aduertit de pluficurs chofes :… | ce titre de sainteté pris en ce sens, ne peut convenir qu’à Dieu seul. Or, ‖ l'Écriture disant que Dieu est saint nous advertit de plusieurs choses : en | ✅ continu |
| 2/3 | …e noftre exhortation. L'E(criture nous propofe plufieurs exemples à imiter. **‖** De SERMONS 109 imiter.Elle nous propofe la promptitude des An- ges à execut… | la seconde partie de notre exhortation. L'Écriture nous propose plusieurs exemples à ‖ imiter. Elle nous propose la promptitude des Anges à exécuter les commandements de | ✅ continu |
| 3/4 | …tourne ia- mais du {entier de iuftice , & de la fidelité qu’il doit à Dieu. **‖** Car Ditueft ferme en fes confeils,& ne change iamais de volonté.ll n’y à en… | du sentier de justice, et de la fidélité qu’il doit à Dieu. ‖ Car Dieu est ferme en ses conseils, et ne change jamais de volonté | ✅ continu |
| 4/5 | …Aemeraire, & pleine de prefomption ; fi Dicu44: mefmic\ne l’auoit commandé. **‖** Et ce comman- dernont d'afre parféies comme Dien' ef parfass ; De- sait pou… | imitation téméraire, et pleine de présomption ; si Dieu même ne l'avait commandé. ‖ Et ce commandement d’être parfaits comme Dieu est parfait, devait pour nous | ✅ continu |
| 5/6 | … parlant par (es Apoftres S. Iean & S.Paul 17h. nous a predites. ' 3. Æpoc. **‖** Mais pout reuenir à la vraye imitation de Dieu '3- © !7- & de (a fainéteté … | Dieu parlant par ses Apôtres S. Jean et S. Paul nous a prédites. ‖ Mais pour revenir à la vraie imitation de Dieu et de sa sainteté | ✅ continu |
| 6/7 | …ersen laterre. { 8. Son affiduité en prieres nous et vn exem- ple à imiter. **‖** Car fi celui qui auoit en (a main touw- te plenitude de biens a efté fi aff… | en la terre. 8. Son assiduité en prières nous est un exemple à imiter. ‖ Car si celui qui avait en sa main toute plénitude de biens a | ✅ continu |
| 7/8 | …6 L IL Decape - ; l’Apocalyple , qu'il à fur fon chef plufieurs dia- demes. **‖** Mais pour reuenit à nous mefmes, & clorre ce- fte exhortation » fouvenons n… | est dit au 19. de l'Apocalypse, qu'il a sur son chef plusieurs diadèmes. ‖ Mais pour revenir à nous-mêmes, et clorre cette exhortation, souvenons-nous que | ✅ continu |

## DuMoulin_S_50_Apocalypse : 7 morceaux, 6 jointures

Log de l'exécution (contrôle de continuité) : `6 jointure(s) contrôlée(s), aucun problème`

| Jointure | Coupure dans l'OCR (fin ‖ début) | Texte final à la jointure | Contrôle |
|---|---|---|---|
| 1/2 | …au comble,& au plus haut de leur profperité font à la veille de leur ruine. **‖** Item eoioignant la beatitude auec la fain&e- té, il declare que la beatitud… | au plus haut de leur prospérité sont à la veille de leur ruine. ‖ Item conjoignant la béatitude avec la sainteté, il déclare que la béatitude n | ✅ continu |
| 2/3 | …ent » & pource que - Ceux qui meurent fe plaignent du mal qu’ils fen- tent. **‖** Mais nos (ens ne recognoiffent pas en quoy it l'horreur de la mort » ni pou… | sentiment, et pource que ceux qui meurent se plaignent du mal qu'ils sentent. ‖ Mais nos sens ne reconnaissent pas en quoi gît l'horreur de la | ✅ continu |
| 3/4 | … pour contempler les œuvres de ieû » & remarquer le cours de fa prouidence. **‖** Ellen’a point d'oreilles pour reccuoir la doétri- “ne celefte. Elle n’a ni … | pour contempler les œuvres de Dieu, et remarquer le cours de sa providence. Elle n' ‖ a point d'oreilles pour recevoir la doctrine céleste. Elle n'a ni | ✅ continu |
| 4/5 | …nt de la poudre » & que les clements rendrone ce qu’ils ont receu en depot. **‖** Cette premiere refurrection n’eft autre chofe que la regeneration & renouuc… | poudre, et que les éléments rendront ce qu'ils ont reçu en dépôt. ‖ Cette première résurrection n’est autre chose que la régénération et renouvellement de | ✅ continu |
| 5/6 | …rompette qui encous tagc les combazcans » & n'entre point en la ba- taille. **‖** Cette œuvre tant excellente ne vient pas de l’eloquence » ni des paroles pe… | à un trompette qui encourage les combattants, et n'entre point en la bataille. ‖ Cette œuvre tant excellente ne vient pas de l’éloquence, ni des paroles | ✅ continu |
| 6/7 | …l'auancer » nousemployans à noftre propre faluc aucc crainte & tremblement. **‖** A cela nous fommesexhortez par la briefveté de la vie prefente , par l'ince… | à l’avancer, nous employant à notre propre salut avec crainte et tremblement. ‖ À cela nous sommes exhortés par la brièveté de la vie présente, par | ✅ continu |

## Durant_S_25_Tentation-16 : 8 morceaux, 7 jointures

Log de l'exécution (contrôle de continuité) : `7 jointure(s) contrôlée(s), aucun problème`

| Jointure | Coupure dans l'OCR (fin ‖ début) | Texte final à la jointure | Contrôle |
|---|---|---|---|
| 1/2 | … oblige de cheminer auec modettie , honneur , & re- fpe&, en leur prefence. **‖** La femme, à caufe des Anges ; doit auoir fur la tefte vne enfcigne qu’elle … | cela nous oblige de cheminer avec modestie, honneur, et respect, en leur présence. ‖ La femme, à cause des Anges, doit avoir sur la tête une enseigne | ✅ continu |
| 2/3 | …x , pource qu’auec eux nous honore- rons & adorerons parfaitement lEternel. **‖** Padioufte encor ce mot , pour l’honneur fpecial que nous deués aux Prophete… | la compagnie des bienheureux, pource qu'avec eux nous honorerons et adorerons parfaitement l'Éternel. J'ajoute encore ‖ ce mot, pour l'honneur spécial que vous devez aux prophètes et aux | ✅ continu, relu à la main : « …parfaitement l'Éternel. J'ajoute encore ce mot… ». Le repère ‖ est décalé de 3 mots par l'alignement. |
| 3/4 | …l Dieu,Pere, Fils, & $.Efprit: comme nous venons maintenant de le verifier. **‖** Mais d'ici naift vne quettion: car puis qu’il fautadorèr le Fils ; & puis q… | Dieu, Père, Fils, et saint Esprit : comme nous venons maintenant de le vérifier. ‖ Mais d'ici naît une question : car puisqu'il faut adorer le Fils | ✅ continu |
| 4/5 | …uinité de- menre le feul & parfait obiect de noftre adora- tion religieule. **‖** Tu adoreras donc le Seigneur ton Dieu, & À lui ul tu feruiras. Or n’entrepr… | telle forte que sa Divinité demeure le seul et parfait objet de notre adoration religieuse. ‖ Tu adoreras donc le Seigneur ton Dieu, et à lui seul tu serviras | ✅ continu |
| 5/6 | …fté tenu en difcipline & conduite fous la pedagogie des ceremonies delaLoi. **‖** Mais fous l’Euangile voici le feruice reli- gieux auquel Dieu nous oblige’ … | enfance, a été tenu en discipline et conduite sous la pédagogie des cérémonies de la Loi. ‖ Mais sous l'Évangile voici le service religieux auquel Dieu nous oblige extérieurement | ✅ continu |
| 6/7 | …iours prefts & de donner lieu à la raifon,& d'en payer nos plus contraires. **‖** Autrement tu cs mautais aduocat de la caufe de Dieu ; la force de la verité… | de donner lieu à la raison, et d'en payer nos plus contraires. ‖ Autrement tu es mauvais avocat de la cause de Dieu ; la force de | ✅ continu |
| 7/8 | …e grace & gloire & n’efpargne aucün bien à ceux qui cheminent en integrité. **‖** Mais voici encor vne obferuation bien im- portante : car quand Iefus Chrift… | et gloire et n'épargne aucun bien à ceux qui cheminent en intégrité. ‖ Mais voici encore une observation bien importante : car quand Jésus Christ applique à | ✅ continu |

## Flechier_S_17_Envie : 7 morceaux, 6 jointures

Log de l'exécution (contrôle de continuité) : `6 jointure(s) contrôlée(s), aucun problème`

| Jointure | Coupure dans l'OCR (fin ‖ début) | Texte final à la jointure | Contrôle |
|---|---|---|---|
| 1/2 | …& de l’horreur pour ce péché. Mais j ai des chofes plus importantes à dire. **‖** Plus un vice participe à la nature du démon, qui eft le principe du péché &… | horreur pour ce péché. Mais j'ai des choses plus importantes à dire. ‖ Plus un vice participe à la nature du démon, qui est le principe | ✅ continu |
| 2/3 | …trouver un remède à {a pauvreté , il trouve l’ac- croiffement de fa misère. **‖** Ce qui doit détourner encore de cette corruption une ame tant foit peu géné… | trouver un remède à sa pauvreté, il trouve l'accroissement de sa misère. ‖ Ce qui doit détourner encore de cette corruption une âme tant soit peu | ✅ continu |
| 3/4 | … poignées de fleurs fur l'Au- tel qu’on veut enfanglanter de fon facrifice. **‖** Y a-til rien de plus indigne & de plus lâche que tous ces moyens dont l’en-… | poignées de fleurs sur l'Autel qu’on veut ensanglanter de son sacrifice. ‖ Y a-t-il rien de plus indigne et de plus lâche que | ✅ continu |
| 4/5 | …propre fupplice celui qui en eft atteint, & qu’il en fait ainfi la juftice. **‖** Mais le dernier carattère que je trouve ence péché, & qui eft le plus terri… | celui qui en est atteint, et qu'il en fait ainsi la justice. ‖ Mais le dernier caractère que je trouve en ce péché, et qui est | ✅ continu |
| 5/6 | …de {petta- ele dans la Religion, être le dévot &: le Prophète de fon temps. **‖** On aimeroit bien à exercer fur des ames fimples un empire abfolu de direion… | spectacle dans la Religion, être le dévot et le Prophète de son temps. ‖ On aimerait bien à exercer sur des âmes simples un empire absolu de | ✅ continu |
| 6/7 | …rme fur la gloire de la beauté & fur le défir ou fur là jaloufie de plaire. **‖** Mais ce qu'il y a de plys- déplorable , dit faint Chryfoftome, c’eft que: c… | de la beauté et sur le désir ou sur la jalousie de plaire. ‖ Mais ce qu'il y a de plus déplorable, dit saint Chrysostome, c | ✅ continu |

## HMonodP_S_41_Crainte : 7 morceaux, 6 jointures

Log de l'exécution (contrôle de continuité) : `6 jointure(s) contrôlée(s), aucun problème`

| Jointure | Coupure dans l'OCR (fin ‖ début) | Texte final à la jointure | Contrôle |
|---|---|---|---|
| 1/2 | …ui représente fidèlement le développe- ment successif de la vie chrétienne. **‖** Le degré inférieur de la crainte de Dieu est la crainte de ses jugements. C… | autre une gradation, qui représente fidèlement le développement successif de la vie chrétienne. ‖ Le degré inférieur de la crainte de Dieu est la crainte de ses | ✅ continu |
| 2/3 | …te son étendue la profondeur de l'amour de Dieu et le prix infini du salut. **‖** Il y a plus encore. Il ne faudrait pas croire que ce soit uniquement comme … | la profondeur de l’amour de Dieu et le prix infini du salut. ‖ Il y a plus encore. Il ne faudrait pas croire que ce soit | ✅ continu |
| 3/4 | …nce marchent devant lui, la force et l’excellence sont dans son sanctuaire. **‖** Familles des peuples, prosternez-vous devant l'Eternel avec une sainte magn… | magnificence marchent devant lui, la force et l’excellence sont dans son sanctuaire. ‖ Familles des peuples, prosternez-vous devant l'Éternel avec une sainte magnificence ; vous | ✅ continu |
| 4/5 | …dance du siècle, et de ré- tablir dans les cœurs la crainte du nom de Dieu. **‖** Mais ce n’est pas là encore le degré le plus élevé de la crainte de Dieu, n… | siècle, et de rétablir dans les cœurs la crainte du nom de Dieu. ‖ Mais ce n’est pas là encore le degré le plus élevé de | ✅ continu |
| 5/6 | …ce péché que Dieu nous pardonne , et qu’il oublie dans son amour pour nous! **‖** Mais il y a plus encore, et ce n’est pas seulement parce que Dieu nous pard… | que Dieu nous pardonne , et qu’il oublie dans son amour pour nous! ‖ Mais il y a plus encore, et ce n’est pas seulement parce | ✅ continu |
| 6/7 | …plus puissant que tous les discours , combien le Seigneur doit être craint. **‖** Elle vous prêche la crainte de son jugement, puis- ! Prèché un jour de comm… | est plus puissant que tous les discours, combien le Seigneur doit être craint. ‖ Elle vous prêche la crainte de son jugement, puisqu’elle vous montre ce | ✅ continu |

## Jaquelot_S_29_Messie : 4 morceaux, 3 jointures

Log de l'exécution (contrôle de continuité) : `3 jointure(s) contrôlée(s), aucun problème`

| Jointure | Coupure dans l'OCR (fin ‖ début) | Texte final à la jointure | Contrôle |
|---|---|---|---|
| 1/2 | …. Il feroit inutile de vous expliquer en détail la jufteffe de cet emblême. **‖** Il vaut mieux fe contenter de, À 3 —_ € La Maniftflation ivre fa penfée du … | Il serait inutile de vous expliquer en détail la justesse de cet emblème. ‖ Il vaut mieux se contenter de, suivre sa pensée du Prophète, qui nous | ✅ continu |
| 2/3 | …ez le Seigneur pendant qu’il fe trouve. Parlons préfentement de la lumiére. **‖** CINQUIEME RÉFLEXION. : ‘ \ Le Soleil de Juftice & de vérité s’eft levé fur … | cherchez le Seigneur pendant qu'il se trouve. Parlons présentement de la lumière. ‖ CINQUIÈME RÉFLEXION. Le Soleil de justice et de vérité s'est levé sur | ✅ continu |
| 3/4 | …t jamais été, il faut auffi remar- - quer que les grands avantages, qui en. **‖** Téfultent , n’apartiennent qu’à ceux qui vivent dans la piété & dans la fai… | ont jamais été, il faut aussi remarquer que les grands avantages, qui en. Résultent, ‖ n'appartiennent qu'à ceux qui vivent dans la piété et dans la | ✅ continu |

## Jaquelot_S_38_Triomphe : 4 morceaux, 3 jointures

Log de l'exécution (contrôle de continuité) : `jointure 1/2 : la SUITE (contexte) a été recopiée en fin de morceau 1 ¦ à corriger`; `3 jointure(s) contrôlée(s), aucun problème`

| Jointure | Coupure dans l'OCR (fin ‖ début) | Texte final à la jointure | Contrôle |
|---|---|---|---|
| 1/2 | …ire à la récompenfe. C’eft ce que FEcriture apelle , étre fauvé par la foi. **‖** Quoi de plus jufte, je vous fuplie , que de croire ici bas aux promeffes de… | récompense. C'est ce que l'Écriture appelle, être sauvé par la foi. ‖ Quoi de plus juste, je vous supplie, que de croire ici-bas aux | ✅ continu |
| 2/3 | …it glo- 64) I, Core XV. ' Le Triomphe de la Morts 161 Tieux de fon tombeau. **‖** C’eft aaffi la rai- fon Jour laquelle la promeffe claire &c: formelle de la… | de la mort et du sépulcre, lorsqu’il sortit glorieux de son tombeau. ‖ C'est aussi la raison pour laquelle la promesse claire et formelle de | ✅ continu |
| 3/4 | …s diront, quand nous pene fons au moment redoutable de la mort. APLIÇATION. **‖** On ne doit pas trouver étrange, que les Fidéles aiment cette vie , tant qu’… | cœurs nous diront, quand nous pensons au moment redoutable de la mort. APPLICATION. ‖ On ne doit pas trouver étrange, que les Fidèles aiment cette vie, tant | ✅ continu |

## LeFaucheur_S_24_Ps-2 : 5 morceaux, 4 jointures

Log de l'exécution (contrôle de continuité) : `4 jointure(s) contrôlée(s), aucun problème`

| Jointure | Coupure dans l'OCR (fin ‖ début) | Texte final à la jointure | Contrôle |
|---|---|---|---|
| 1/2 | …euvent appartenir à vne ‘fimple eaeature , mais à Iefus Chrilt feu- lement. **‖** Secondement , parce qu’âu 4 chap. des Attés, ce Pfeaume elft expref- fément… | Toutes lesquelles choses, ne peuvent appartenir à une simple créature, mais à Jésus-Christ seulement. ‖ Secondement, parce qu'au 4e chapitre des Actes, ce Psaume est expressément appliqué | ✅ continu |
| 2/3 | …, authorifeut ces furcurs brutales, c’cft ce qui furpaflc cour cftonnement. **‖** Remarquez, en fecond lieu,la defcri- ption que fair le Prophete de la malic… | en honneur et en dignité, autorisent ces furies brutales, c'est ce qui surpasse tout étonnement. ‖ Remarquez, en second lieu, la description que fait le Prophète de la malice | ✅ continu |
| 3/4 | …fait aux marteaux, quand, à force d’en recevoirles coups, élle les bri- fe. **‖** Nous leur en faifons, mais c’eft, qu’en leur donnant à manger & à boire, & … | fait aux marteaux, quand, à force d'en recevoir les coups, elle les brise. ‖ Nous leur en faisons, mais c'est, qu'en leur donnant à manger | ✅ continu |
| 4/5 | …es fondemens , & de trop avantageufes promeffes , pour eftre jamais ruinée. **‖** Car comme fous l’ancien- ne alliançe, Dieu lui difoit, NuÂes armures forgée… | de trop fermes fondements, et de trop avantageuses promesses, pour être jamais ruinée. ‖ Car comme sous l'alliance, Dieu lui disait, Nulles armures forgées contre toi | ✅ continu |

## LeFaucheur_S_68_Ps-16-8-11 : 7 morceaux, 6 jointures

Log de l'exécution (contrôle de continuité) : `jointure 2/3 : point ajouté au milieu d'une phrase (« …n vers et en poussière, comme celle des. » / « autres hommes se pourrit dans leur tombe… ») ¦ corrigé au recollage`

| Jointure | Coupure dans l'OCR (fin ‖ début) | Texte final à la jointure | Contrôle |
|---|---|---|---|
| 1/2 | … mes ennemis ne prevaillent; & que Je ne fuécombe fbus la: pcfanteurde mes. **‖** Maux: Pourtantmon.cœur s'efl Éjouts l'ay ‘ptig vi nouveau EVurage au milieu… | ennemis ne prévalent; et que je ne succombe sous la pesanteur de mes. ‖ Maux : Pourtant mon cœur s'est réjoui, j'ai pris un nouveau courage | ✅ continu |
| 2/3 | …’y laifferas pas refoudre ma chair en vers & en poufficre, comme celle des. **‖** L 3 autres - ” ve SErMoN VI autres hommes fe pourrit dans leur tom- beau. N… | laisseras pas résoudre ma chair en vers et en poussière, comme celle des ‖ autres hommes se pourrit dans leur tombeau. Nos adversaires n’entendent pas ainsi | ✅ continu |
| 3/4 | …ce ef} un raffafie- ment de joye. Ily à plaifance c» te dextre pour jamais. **‖** Paroles qui pedvent bien en quelque façô être raportées à David; pour figni… | un rassasiement de joie. Il y a plaisance en ta dextre pour jamais. ‖ Paroles qui peuvent bien en quelque façon être rapportées à David ; pour signifier | ✅ continu |
| 4/5 | …à. Car qui est-ce qui intentera accufé- tion contre les eleus de Dien. 8ec. **‖** Pour la confolation & pour la joye nous la de- vons avoir .tres- grande qua… | côté-là. Car qui est-ce qui intentera accusation contre les élus de Dieu ? etc. ‖ Pour la consolation et pour la joie, nous la devons avoir très grande | ✅ continu |
| 5/6 | …e reflufciter cn ignominie pour éftre damné à jamais comme les reprou- vez? **‖** Tu voudrois qu’il reffufcitat cha- Gun à part peu de tempsaprés fon trepas … | voulait ressusciter, te ressusciter en ignominie pour être damné à jamais comme les réprouvés ? ‖ Tu voudrais qu’il ressuscitât chacun à part peu de temps après son | ✅ continu |
| 6/7 | …doit venir viendra , & mettra on evidence fa. gloire 8 celle de fon peuple. **‖** Soyons feulement foigneux de bien viure & de - le fervir avec une vraye dev… | venir viendra, et mettra en évidence sa gloire et celle de son peuple. ‖ Soyons seulement soigneux de bien vivre et de le servir avec une vraie | ✅ continu |

## Morus_S_20_Philippiens-I : 6 morceaux, 5 jointures

Log de l'exécution (contrôle de continuité) : `5 jointure(s) contrôlée(s), aucun problème`

| Jointure | Coupure dans l'OCR (fin ‖ début) | Texte final à la jointure | Contrôle |
|---|---|---|---|
| 1/2 | …mage, comme quand le même difoit aux Gal tes,que Chrift {ec formoit en eux. **‖** Dans nôtre Texte il ne fe peut prendre . ni en li premiére ni en la fcconde… | comme quand le même disait aux Galates, que Christ se formait en eux. ‖ Dans notre texte il ne se peut prendre ni en la première ni | ✅ continu |
| 2/3 | … nos biens, ¦ comme dit le Pfalmitte, ne fauroit parve- nir jufques à Diev. **‖** Quoy denc? pourqucy l’Apôtre nous parle-t-il icy d’un gain, non fimplement … | de nos biens, comme dit le psalmiste, ne saurait parvenir jusque à Dieu. ‖ Quoi donc ? pourquoi l'Apôtre nous parle-t-il ici d'un gain | ✅ continu |
| 3/4 | …- border à cet heureux rivage côme il aloit en Damas, où il a trouvé Chrit. **‖** C'eft donc à bon droit qu’il F+ vante que Chiitt luv eft gain,encore q'’il … | cet heureux rivage comme il allait en damas, où il a trouvé Christ. ‖ C'est donc à bon droit qu'il se vante que Christ lui | ✅ continu |
| 4/5 | …fi dans le che- min du falut, avec un zele & vne affi- > duité nompareille. **‖** Pourquoy ne defire- t-il de vivre pourleur bien ? Nous répon- dons qu’il fa… | et par ainsi dans le chemin du salut, avec un zèle et une assiduité nonpareille. ‖ Pourquoi ne désire-t-il de vivre pour leur bien ? Nous répondons qu | ✅ continu |
| 5/6 | …on ame en tes mains je viens rendre ; car tu mas racheté, à Dies de verité. **‖** SERMON… | mains je viens rendre ; car tu m’as racheté, ô Dieu de vérité. ‖ Sermon | ✅ continu |

## Morus_S_95_2Corinthiens-XII-2 : 7 morceaux, 6 jointures

Log de l'exécution (contrôle de continuité) : `6 jointure(s) contrôlée(s), aucun problème`

| Jointure | Coupure dans l'OCR (fin ‖ début) | Texte final à la jointure | Contrôle |
|---|---|---|---|
| 1/2 | …i préferer Saint Paul à Saint Pierre , ni égaler Saint Pierre à Saint Paul. **‖** Et de fait nous pouvons dire fans en- treprendre une éxacte comparaifon de … | préférer Saint Paul à Saint Pierre, ni égaler Saint Pierre à Saint Paul. ‖ Et de fait nous pouvons dire sans entreprendre une exacte comparaison de ces | ✅ continu |
| 2/3 | …iére qu'il fait à Dieu, & énia troi ‘ fiéme , la réponce que Dieu lui fair. **‖** Quelle eft donc fon écharde ? il nous c£ mal aife de le deviner puis que lu… | qu'il fait à Dieu, et en troisième, la réponse que Dieu lui fait. ‖ Quelle est donc son écharde ? Il nous est malaisé de le deviner, puisque | ✅ continu |
| 3/4 | … afflitions , beaucoup plutôr cûc # éxcepté fes paffions & fes convoitifes. **‖** Mais laiffons à part cette inrerpréta- tion, digne de ceux qui voudroienr a… | même ses afflictions, beaucoup plutôt eût-il excepté ses passions et ses convoitises. ‖ Mais laissons à part cette interprétation, digne de ceux qui voudraient avoir Saint | ✅ continu |
| 4/5 | …ompte , où l’orgüeil qu’elle ne créve, Ou la monca- gne qu’elle n’abbaiffe? **‖** Mais ce n’étoit pas l’écharde de Sainte Paul, il n’avoig à perdre ni des gr… | l'orgueil qu'elle ne crève, Ou la montagne qu'elle n'abaisse ? ‖ Mais ce n'était pas l'écharde de saint Paul, il n'avait | ✅ continu |
| 5/6 | …es piéces de bois pointu qui bleffent leurs piés & tranfpercent leur chair. **‖** Ecce qui eft confiderable , ce terme que nous avons traduit étharde , figni… | des pièces de bois pointu qui blessent leurs pieds et transpercent leur chair. Ce ‖ qui est considérable, ce terme que nous avons traduit écharde, signifie une espèce | ✅ continu |
| 6/7 | …ueux de Corinthe, qu’un tel foit Hvré à Satan. à la deftru&fon de la-chair. **‖** Il livre les autres à Satan, & il ne s’en fauroit délivrer lui-même : icy n… | qu’un tel soit livré à Satan à la destruction de la chair. ‖ Il livre les autres à Satan, et il ne s'en saurait délivrer | ✅ continu |

## Nardin_S_46_Trinite8 : 11 morceaux, 10 jointures

Log de l'exécution (contrôle de continuité) : `jointure 6/7 : phrase tronquée en fin de morceau 6 (« …a miséricorde du Père.`; `10 jointure(s) contrôlée(s), aucun problème`

| Jointure | Coupure dans l'OCR (fin ‖ début) | Texte final à la jointure | Contrôle |
|---|---|---|---|
| 1/2 | …demens fur lefquels ils établiffent les efpérances qu’ils fe font du falut. **‖** H faut leur decouvrir, le mauvais état de fauf feté & de tromperie dans leq… | fondements sur lesquels ils établissent les espérances qu’ils se font du salut. Il ‖ faut leur découvrir le mauvais état de fausseté et de tromperie dans lequel | ✅ continu |
| 2/3 | …urri & corrompu » qui ne fauroit produire que des fruits pourris & méchans. **‖** Cleft pourquoi l’écriture fainte témoigne que les méchans font expers à mal… | suc pourri et corrompu, qui ne saurait produire que des fruits pourris et méchants. C'est ‖ pourquoi l'écriture sainte témoigne que les méchants sont experts à mal faire | ✅ continu |
| 3/4 | …uvais qu'en fac pourri & corrompu » il ne peur faire que desfruits mauvais. **‖** Mais fui i fraits. faut favoir ce que c’eft que les bons fruits » Sc ce que… | un suc pourri et corrompu, il ne peut faire que des fruits mauvais. ‖ Mais s'il faut savoir ce que c'est que les bons fruits | ✅ continu |
| 4/5 | …s y ne crains tu point cette terrible fen- tence de Jéfus dans nôtre texte? **‖** Tous arbre qui ne fait point de bons fruits s'es va être coupé Cr jette au … | bons, ne crains-tu point cette terrible sentence de Jésus dans notre texte ? Tout ‖ arbre qui ne fait point de bons fruits s'en va être coupé | ✅ continu |
| 5/6 | … des faux Chrêtiens à ui toures ces chofes ne fervent de rien pour lefalut. **‖** Deforte que route ce {es extérieures qui font bonnes fans doute en elles mê… | des faux chrétiens à qui toutes ces choses ne servent de rien pour le salut. De sorte ‖ que toutes ces œuvres extérieures qui sont bonnes sans doute en elles-mêmes | ✅ continu, relu à la main : « …pour le salut. De sorte que toutes ces œuvres… ». Le repère ‖ est décalé de 2 mots. |
| 6/7 | …sallons tâcher de vous aprendre dans la feconde partie de cette méditation. **‖** Le premier caraGtére d’un bon Chrêtien ; c’eft d'être un bon arbre , c'eft … | nous allons tâcher de vous apprendre dans la seconde partie de cette méditation. ‖ Le premier caractère d'un bon chrétien ; c'est d'être un bon | ✅ continu |
| 7/8 | …ouveau luc , & par conféquent capable de produire auffi quelques ns fruits. **‖** Tfaue Defirés vous donc, chéres ames, de devenir de bons arbres, cherchés l… | un nouveau suc, et par conséquent capable de produire aussi quelques bons fruits. Désirez- ‖ vous donc, chères âmes, de devenir de bons arbres, cherchez la miséricorde de | ✅ continu |
| 8/9 | …roduire de 2, bons fruits : C’eft Une fuite néceflairé“du premier Caratére. **‖** Quand une ame Ils produi- eft une fois jultifiée par la grace & par la mifé… | que de produire de bons fruits : c'est une suite nécessaire du premier caractère. ‖ Quand une âme est une fois justifiée par la grâce et par la | ✅ continu |
| 9/10 | …t des bons fruits & des chofes en quoi tu feras la volonté du Père célelte. **‖** Maisce n'eft pas affés de favoir la volonté du Pére; il faut aufi la faire … | bons fruits et des choses en quoi tu feras la volonté du Père céleste. Mais ce ‖ n'est pas assez de savoir la volonté du Père ; il faut aussi | ✅ continu |
| 10/11 | …un peu , nous trouverons auffi dans nous une grande mifére fur cet article. **‖** Hélas! que nous fommes froids & languiffans pour les biens invifibles & fpi… | un peu, nous trouverons aussi dans nous une grande misère sur cet article. ‖ Hélas ! que nous sommes froids et languissants pour les biens invisibles et spirituels | ✅ continu |

## Reguis_S_43_Service : 6 morceaux, 5 jointures

Log de l'exécution (contrôle de continuité) : `jointure 2/3 : point ajouté au milieu d'une phrase (« …pas soi-même à des abstinences et à des. » / « jeûnes mille fois plus sévères que ceux … ») ¦ corrigé au recollage`

| Jointure | Coupure dans l'OCR (fin ‖ début) | Texte final à la jointure | Contrôle |
|---|---|---|---|
| 1/2 | …nt à votre bien - être , à votre fanté , à votre repos , à votre for- tune. **‖** Quel eft donc le changement que la piété apportera dans votre perfonne 5 & … | nécessairement à votre bien-être, à votre santé, à votre repos, à votre fortune. ‖ Quel est donc le changement que la piété apportera dans votre personne et | ✅ continu |
| 2/3 | …-' tées à? Mais ne fe condamne-t-on pas loi-même à des abftinences & à des. **‖** APRÈS LA PENTECÔTE. 43 jeûnes mille fois plus {évères que ceux de l’Églife … | se condamne-t-on pas soi-même à des abstinences et à des ‖ jeûnes mille fois plus sévères que ceux de l’Église, pour rétablir ou | ✅ continu |
| 3/4 | … feulement pofli- bles mais facile & agréable , avecle fecours de la grace. **‖** Je lailfe toutes ces réflexions,& je demande s’il n’en coûte rien aux péche… | non seulement possible, mais facile et agréable, avec le secours de la grâce. ‖ Je laisse toutes ces réflexions, et je demande s'il n'en coûte | ✅ continu |
| 4/5 | …recevoir dans le Ciel la récompenfe ‘de votre vertu 8 de vos bohhes &uvres. **‖** Voicimaintet nant quel fera vatrerfort ; fi vous pre= nez le parti-de vous … | de recevoir dans le Ciel la récompense de votre vertu et de vos bonnes œuvres. Voici maintenant ‖ quel sera votre fort ; si vous prenez le parti de vous livrer au | ✅ continu, relu à la main : « …de vos bonnes œuvres. Voici maintenant quel sera… ». L'étiquette d'interface « Extrait de code » qui s'y trouvait a été retirée (bug d'extraction corrigé). Le repère ‖ est décalé de 2 mots. |
| 5/6 | … de l’humanité , & faire des membres de J. C. les membres d'une proffituée. **‖** Mais les peines d’efprit & de cœur, ne feront pas les feules épines que vou… | l’humanité, et faire des membres de J. C. les membres d'une prostituée. ‖ Mais les peines d'esprit et de cœur, ne feront pas les seules | ✅ continu |

## Scholl_S_13_Necessite-Esprit : 5 morceaux, 4 jointures

Log de l'exécution (contrôle de continuité) : `4 jointure(s) contrôlée(s), aucun problème`

| Jointure | Coupure dans l'OCR (fin ‖ début) | Texte final à la jointure | Contrôle |
|---|---|---|---|
| 1/2 | …ent en eux, avec confusion de face, des restes de leur premier aveuglement. **‖** Que si, des fidèles, nous tournons nos regards sur les hommes qui résistent… | souvent en eux, avec confusion de face, des restes de leur premier aveuglement. ‖ Que si, des fidèles, nous tournons nos regards sur les hommes qui résistent | ✅ continu |
| 2/3 | …s les âmes, est une œuvre qui n’est au pouvoir d'aucun homme d’accom- plir. **‖** Cependant, quoique ce soit l’œuvre de Dieu, gardez-vous de croire, dans le … | âmes, est une œuvre qui n'est au pouvoir d'aucun homme d'accomplir. ‖ Cependant, quoique ce soit l’œuvre de Dieu, gardez-vous de croire, dans | ✅ continu |
| 3/4 | …eil, dans le salut de Phomme pécheur? Le Seigneur « guet le cœur de. Lydie. **‖** Ainsi, mes Frères , si vos cœurs ont été ouverts à la parole divine, si vou… | le salut de l'homme pécheur ? Le Seigneur ouvrit le cœur de Lydie. ‖ Ainsi, mes Frères, si vos cœurs ont été ouverts à la parole divine | ✅ continu |
| 4/5 | …e l’amour de Dieu et du dévoue- ment à sa volonté naître au dedans de vous. **‖** Il vous sera donné de vous consacrer à lui sans réserve. — Et aussi certain… | de Dieu et du dévouement à sa volonté naître au dedans de vous. ‖ Il vous sera donné de vous consacrer à lui sans réserve. — Et aussi | ✅ continu |
