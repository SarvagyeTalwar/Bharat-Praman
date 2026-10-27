"""Curated one-line explanations for major IPC (Indian Penal Code) sections.

These are the sections that actually appear in the Bharat Praman politician
graph (Section.code). Values are concise, plain-English one-liners intended
for the glossary UI. Sections not listed here are omitted from the UI.

Note: the graph data predates the Bharatiya Nyaya Sanhita (BNS, 2024), so
these are IPC references. Major BNS mappings are noted inline where relevant.
"""

import re

# code -> one-line explanation
EXPLANATIONS = {
    "34": "Acts done by several persons in furtherance of a common intention.",
    "109": "Abetment of an offence (punishment when no express provision).",
    "114": "Abettor present when the offence is committed.",
    "120B": "Criminal conspiracy (punishment).",
    "141": "Unlawful assembly (definition: 5+ persons, common object).",
    "143": "Unlawful assembly (punishment).",
    "144": "Joining an unlawful assembly armed with a deadly weapon.",
    "145": "Joining or continuing in an unlawful assembly after dispersal order.",
    "146": "Rioting (definition: force or violence by unlawful assembly).",
    "147": "Rioting (punishment).",
    "148": "Rioting while armed with a deadly weapon.",
    "149": "Every member of an unlawful assembly guilty of the offence committed.",
    "152": "Assaulting a public servant who is suppressing a riot.",
    "153": "Wantonly giving provocation with intent to cause a riot.",
    "153A": "Promoting enmity between groups on grounds of religion, race, etc.",
    "153B": "Imputations or assertions prejudicial to national integration.",
    "171B": "Bribery in connection with elections.",
    "171C": "Undue influence at an election.",
    "171E": "Punishment for bribery in connection with elections.",
    "171F": "Punishment for undue influence or personation at elections.",
    "171G": "False statement in connection with an election.",
    "171H": "Illegal payments in connection with an election.",
    "186": "Obstructing a public servant in the discharge of duty.",
    "188": "Disobedience of an order duly promulgated by a public servant.",
    "189": "Threat of injury to a public servant.",
    "201": "Causing disappearance of evidence, or giving false information.",
    "269": "Negligent act likely to spread infection of a disease.",
    "270": "Malignant act likely to spread infection of a disease.",
    "271": "Disobedience to a quarantine rule.",
    "283": "Danger or obstruction in a public way or line of navigation.",
    "290": "Public nuisance (punishment).",
    "294": "Obscene acts or songs in a public place.",
    "295": "Injuring or defiling a place of worship with intent to insult religion.",
    "295A": "Deliberate and malicious acts intended to outrage religious feelings.",
    "302": "Murder (punishment).",
    "304": "Culpable homicide not amounting to murder (punishment).",
    "304A": "Causing death by a rash or negligent act.",
    "307": "Attempt to murder.",
    "323": "Voluntarily causing hurt (punishment).",
    "324": "Voluntarily causing hurt by dangerous weapons or means.",
    "325": "Voluntarily causing grievous hurt (punishment).",
    "326": "Voluntarily causing grievous hurt by dangerous weapons or means.",
    "332": "Voluntarily causing hurt to deter a public servant from duty.",
    "336": "Act endangering the life or personal safety of others.",
    "337": "Causing hurt by an act endangering life or personal safety.",
    "338": "Causing grievous hurt by an act endangering life or personal safety.",
    "341": "Wrongful restraint (punishment).",
    "342": "Wrongful confinement (punishment).",
    "352": "Assault or criminal force otherwise than on grave provocation.",
    "353": "Assault or criminal force to deter a public servant from duty.",
    "354": "Assault or criminal force to a woman with intent to outrage her modesty.",
    "354A": "Sexual harassment (unwelcome physical contact, demand for sexual favours).",
    "354B": "Assault or use of force with intent to disrobe a woman.",
    "354C": "Voyeurism (watching or capturing a woman's private acts).",
    "354D": "Stalking (following or contacting a woman despite clear disinterest).",
    "376": "Punishment for rape.",
    "379": "Punishment for theft.",
    "384": "Punishment for extortion.",
    "406": "Punishment for criminal breach of trust.",
    "409": "Criminal breach of trust by a public servant, banker or agent.",
    "417": "Punishment for cheating.",
    "418": "Cheating with knowledge of likely wrongful loss to the victim.",
    "419": "Cheating by personation.",
    "420": "Cheating and dishonestly inducing delivery of property.",
    "426": "Punishment for mischief.",
    "427": "Mischief causing damage to property.",
    "431": "Mischief causing damage to a public road, bridge or telegraph.",
    "435": "Mischief by fire or explosive substance with intent to cause damage.",
    "436": "Mischief by fire or explosive substance with intent to destroy a house.",
    "447": "Punishment for criminal trespass.",
    "448": "Punishment for house-trespass.",
    "452": "House-trespass after preparation for hurt, assault or wrongful restraint.",
    "465": "Punishment for forgery.",
    "467": "Forgery of a valuable security, will, or authority.",
    "468": "Forgery for the purpose of cheating.",
    "471": "Using as genuine a forged document.",
    "477A": "Falsification of accounts.",
    "498A": "Cruelty by husband or relatives of husband.",
    "499": "Defamation (definition).",
    "500": "Defamation (punishment).",
    "503": "Criminal intimidation (definition).",
    "504": "Intentional insult with intent to provoke a breach of the peace.",
    "505": "Statements conducing to public mischief.",
    "506": "Criminal intimidation (punishment).",
    "506B": "Criminal intimidation by an anonymous communication.",
    "509": "Word, gesture or act intended to insult the modesty of a woman.",
    "511": "Attempt to commit an offence (punishment).",
}


def normalize_code(code: str) -> str:
    """Upper-case and strip a Section code; drop parenthetical subsection
    notation (e.g. '505(2)' -> '505', '153(A)' -> '153A' is NOT dropped
    because the letter is not parenthesized in the canonical form).

    We only upper-case and strip here; exact matching against EXPLANATIONS
    handles the rest. Case-variant duplicates ('120b' vs '120B') collapse here.
    """
    return (code or "").strip().upper()


def explain(code: str):
    """Return the one-line explanation for a section code, or None."""
    return EXPLANATIONS.get(normalize_code(code))
