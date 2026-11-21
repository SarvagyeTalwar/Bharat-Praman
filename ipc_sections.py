"""Curated one-line explanations and 5-pillar statutory classification for IPC sections.

These are the sections that actually appear in the Bharat Praman politician
graph (Section.code). Values are concise, plain-English one-liners intended
for the glossary UI, alongside a statutory severity classification derived
from the 5-pillar framework (punishment ceiling >= 5 years, non-bailability,
offenses against women/children, public order/extortion/state security, and
electoral/financial integrity).

Note: the graph data primarily predates the Bharatiya Nyaya Sanhita (BNS, 2024),
so these are IPC references. Major variant notations are normalized cleanly.
"""

# code -> one-line explanation
EXPLANATIONS = {
    "34": "Acts done by several persons in furtherance of a common intention.",
    "109": "Abetment of an offence (punishment when no express provision).",
    "114": "Abettor present when the offence is committed.",
    "115": "Abetment of offence punishable with death or imprisonment for life.",
    "120B": "Criminal conspiracy (punishment).",
    "121": "Waging, or attempting to wage war, or abetting waging of war, against the Government of India.",
    "121A": "Conspiracy to commit offences punishable by section 121.",
    "124A": "Sedition (exciting disaffection towards the Government established by law).",
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
    "166": "Public servant disobeying law, with intent to cause injury to any person.",
    "167": "Public servant framing an incorrect document with intent to cause injury.",
    "171B": "Bribery in connection with elections.",
    "171C": "Undue influence at an election.",
    "171E": "Punishment for bribery in connection with elections.",
    "171F": "Punishment for undue influence or personation at elections.",
    "171G": "False statement in connection with an election.",
    "171H": "Illegal payments in connection with an election.",
    "177": "Furnishing false information to a public servant.",
    "186": "Obstructing a public servant in the discharge of duty.",
    "188": "Disobedience of an order duly promulgated by a public servant.",
    "189": "Threat of injury to a public servant.",
    "193": "Punishment for false evidence (perjury).",
    "195A": "Threatening any person to give false evidence.",
    "201": "Causing disappearance of evidence, or giving false information.",
    "212": "Harbouring an offender.",
    "223": "Escape from confinement or custody negligently suffered by public servant.",
    "224": "Resistance or obstruction by a person to his lawful apprehension.",
    "225": "Resistance or obstruction to lawful apprehension of another person.",
    "268": "Public nuisance (definition).",
    "269": "Negligent act likely to spread infection of a disease.",
    "270": "Malignant act likely to spread infection of a disease.",
    "271": "Disobedience to a quarantine rule.",
    "279": "Rash driving or riding on a public way.",
    "283": "Danger or obstruction in a public way or line of navigation.",
    "285": "Negligent conduct with respect to fire or combustible matter.",
    "286": "Negligent conduct with respect to explosive substance.",
    "290": "Public nuisance (punishment).",
    "291": "Continuance of nuisance after injunction to discontinue.",
    "292": "Sale, etc., of obscene books or objects.",
    "294": "Obscene acts or songs in a public place.",
    "295": "Injuring or defiling a place of worship with intent to insult religion.",
    "295A": "Deliberate and malicious acts intended to outrage religious feelings.",
    "298": "Uttering words, etc., with deliberate intent to wound religious feelings.",
    "302": "Murder (punishment).",
    "304": "Culpable homicide not amounting to murder (punishment).",
    "304A": "Causing death by a rash or negligent act.",
    "307": "Attempt to murder.",
    "323": "Voluntarily causing hurt (punishment).",
    "324": "Voluntarily causing hurt by dangerous weapons or means.",
    "325": "Voluntarily causing grievous hurt (punishment).",
    "326": "Voluntarily causing grievous hurt by dangerous weapons or means.",
    "332": "Voluntarily causing hurt to deter a public servant from duty.",
    "333": "Voluntarily causing grievous hurt to deter public servant from his duty.",
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
    "355": "Assault or criminal force with intent to dishonour a person.",
    "363": "Punishment for kidnapping.",
    "364": "Kidnapping or abducting in order to murder.",
    "365": "Kidnapping or abducting with intent secretly and wrongfully to confine person.",
    "376": "Punishment for rape.",
    "379": "Punishment for theft.",
    "380": "Theft in dwelling house, etc.",
    "382": "Theft after preparation made for causing death, hurt or restraint.",
    "384": "Punishment for extortion.",
    "385": "Putting person in fear of injury in order to commit extortion.",
    "386": "Extortion by putting a person in fear of death or grievous hurt.",
    "387": "Putting person in fear of death or of grievous hurt, in order to commit extortion.",
    "389": "Putting person in fear of accusation of offence, in order to commit extortion.",
    "392": "Punishment for robbery.",
    "394": "Voluntarily causing hurt in committing robbery.",
    "395": "Punishment for dacoity.",
    "397": "Robbery, or dacoity, with attempt to cause death or grievous hurt.",
    "398": "Attempt to commit robbery or dacoity when armed with deadly weapon.",
    "403": "Dishonest misappropriation of property.",
    "406": "Punishment for criminal breach of trust.",
    "408": "Criminal breach of trust by clerk or servant.",
    "409": "Criminal breach of trust by a public servant, banker or agent.",
    "411": "Dishonestly receiving stolen property.",
    "415": "Cheating (definition).",
    "416": "Cheating by personation (definition).",
    "417": "Punishment for cheating.",
    "418": "Cheating with knowledge of likely wrongful loss to the victim.",
    "419": "Cheating by personation.",
    "420": "Cheating and dishonestly inducing delivery of property.",
    "423": "Dishonest or fraudulent execution of deed of transfer containing false statement.",
    "426": "Punishment for mischief.",
    "427": "Mischief causing damage to property.",
    "431": "Mischief causing damage to a public road, bridge or telegraph.",
    "435": "Mischief by fire or explosive substance with intent to cause damage.",
    "436": "Mischief by fire or explosive substance with intent to destroy a house.",
    "447": "Punishment for criminal trespass.",
    "448": "Punishment for house-trespass.",
    "451": "House-trespass in order to commit offence punishable with imprisonment.",
    "452": "House-trespass after preparation for hurt, assault or wrongful restraint.",
    "454": "Lurking house-trespass or house-breaking in order to commit offence.",
    "457": "Lurking house-trespass or house-breaking by night in order to commit offence.",
    "463": "Forgery (definition).",
    "464": "Making a false document.",
    "465": "Punishment for forgery.",
    "466": "Forgery of record of Court or of public register, etc.",
    "467": "Forgery of a valuable security, will, or authority.",
    "468": "Forgery for the purpose of cheating.",
    "469": "Forgery for purpose of harming reputation.",
    "471": "Using as genuine a forged document.",
    "474": "Having possession of a valuable security or will knowing it to be forged.",
    "477A": "Falsification of accounts.",
    "498A": "Cruelty by husband or relatives of husband.",
    "499": "Defamation (definition).",
    "500": "Defamation (punishment).",
    "501": "Printing or engraving matter known to be defamatory.",
    "502": "Sale of printed or engraved substance containing defamatory matter.",
    "503": "Criminal intimidation (definition).",
    "504": "Intentional insult with intent to provoke a breach of the peace.",
    "505": "Statements conducing to public mischief.",
    "506": "Criminal intimidation (punishment).",
    "506(2)": "Criminal intimidation if threat be to cause death or grievous hurt, etc.",
    "506B": "Criminal intimidation by an anonymous communication.",
    "507": "Criminal intimidation by an anonymous communication.",
    "509": "Word, gesture or act intended to insult the modesty of a woman.",
    "511": "Attempt to commit an offence (punishment).",
}

_VARIANT_MAP = {
    "120B": "120B",
    "120(B)": "120B",
    "294B": "294",
    "294(B)": "294",
    "506(2)": "506(2)",
    "506(II)": "506(2)",
    "506B": "506(2)",
    "506(1)": "506",
    "506(I)": "506",
    "505(2)": "505",
    "505(1)(B)": "505",
    "505(1)": "505",
    "189(2)": "189",
}

_PILLAR_1 = "Pillar 1: Punishment >= 5 Years"
_PILLAR_2 = "Pillar 2: Non-Bailable Violent / Threat Offense"
_PILLAR_3 = "Pillar 3: Crime Against Women & Children"
_PILLAR_4 = "Pillar 4: Public Order, Extortion & State Security"
_PILLAR_5 = "Pillar 5: Electoral & Financial Integrity"

HEINOUS_SPEC: dict[str, dict] = {
    # Pillar 1: Punishment >= 5 Years
    "115": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_1, "max_punishment": "14 Years / 7 Years", "bailable": False},
    "193": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_1, "max_punishment": "7 Years", "bailable": False},
    "195A": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_1, "max_punishment": "7 Years", "bailable": False},
    "201": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_1, "max_punishment": "7 Years (Up to 10 Yrs)", "bailable": False},
    "212": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_1, "max_punishment": "5 Years", "bailable": False},
    "302": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_1, "max_punishment": "Death / Life", "bailable": False},
    "304": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_1, "max_punishment": "Life / 10 Years", "bailable": False},
    "307": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_1, "max_punishment": "Life / 10 Years", "bailable": False},
    "325": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_1, "max_punishment": "7 Years", "bailable": True},
    "326": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_1, "max_punishment": "Life / 10 Years", "bailable": False},
    "333": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_1, "max_punishment": "10 Years", "bailable": False},
    "363": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_1, "max_punishment": "7 Years", "bailable": False},
    "364": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_1, "max_punishment": "Life / 10 Years", "bailable": False},
    "365": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_1, "max_punishment": "7 Years", "bailable": False},
    "380": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_1, "max_punishment": "7 Years", "bailable": False},
    "382": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_1, "max_punishment": "10 Years", "bailable": False},
    "392": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_1, "max_punishment": "10 Years (Up to 14 Yrs)", "bailable": False},
    "394": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_1, "max_punishment": "Life / 10 Years", "bailable": False},
    "395": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_1, "max_punishment": "Life / 10 Years", "bailable": False},
    "397": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_1, "max_punishment": "Min 7 Years", "bailable": False},
    "398": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_1, "max_punishment": "Min 7 Years", "bailable": False},
    "435": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_1, "max_punishment": "7 Years", "bailable": True},
    "436": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_1, "max_punishment": "Life / 10 Years", "bailable": False},
    "452": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_1, "max_punishment": "7 Years", "bailable": False},
    "454": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_1, "max_punishment": "3 to 10 Years", "bailable": False},
    "457": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_1, "max_punishment": "5 to 14 Years", "bailable": False},

    # Pillar 2: Non-Bailable Violent / Threat Offense
    "506(2)": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_2, "max_punishment": "7 Years", "bailable": False},
    "506B": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_2, "max_punishment": "7 Years (Section 506 Part II / Threat)", "bailable": False},

    # Pillar 3: Crime Against Women & Children
    "354": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_3, "max_punishment": "5 Years", "bailable": False},
    "354A": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_3, "max_punishment": "3 Years", "bailable": False},
    "354B": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_3, "max_punishment": "7 Years", "bailable": False},
    "354C": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_3, "max_punishment": "3 to 7 Years", "bailable": False},
    "354D": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_3, "max_punishment": "3 to 5 Years", "bailable": False},
    "376": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_3, "max_punishment": "Death / Life", "bailable": False},
    "498A": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_3, "max_punishment": "3 Years", "bailable": False},
    "509": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_3, "max_punishment": "3 Years", "bailable": False},

    # Pillar 4: Public Order, Extortion & State Security
    "121": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_4, "max_punishment": "Death / Life", "bailable": False},
    "121A": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_4, "max_punishment": "Life / 10 Years", "bailable": False},
    "124A": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_4, "max_punishment": "Life / 3 Years", "bailable": False},
    "153A": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_4, "max_punishment": "3 to 5 Years", "bailable": False},
    "153B": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_4, "max_punishment": "3 to 5 Years", "bailable": False},
    "295": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_4, "max_punishment": "2 Years (Non-Bailable)", "bailable": False},
    "295A": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_4, "max_punishment": "3 Years", "bailable": False},
    "384": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_4, "max_punishment": "3 Years", "bailable": False},
    "385": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_4, "max_punishment": "2 Years (Extortion Attempt)", "bailable": False},
    "386": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_4, "max_punishment": "10 Years", "bailable": False},
    "387": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_4, "max_punishment": "7 Years", "bailable": False},
    "389": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_4, "max_punishment": "10 Years / Life", "bailable": False},
    "505": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_4, "max_punishment": "3 Years", "bailable": False},
    "505(2)": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_4, "max_punishment": "3 Years (Promotes Enmity)", "bailable": False},

    # Pillar 5: Electoral & Financial Integrity
    "171B": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_5, "max_punishment": "1 Year (Electoral Bribery)", "bailable": True},
    "171C": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_5, "max_punishment": "1 Year (Electoral Undue Influence)", "bailable": True},
    "171E": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_5, "max_punishment": "1 Year (Electoral Bribery)", "bailable": True},
    "171F": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_5, "max_punishment": "1 Year (Electoral Personation)", "bailable": True},
    "171G": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_5, "max_punishment": "Fine (False Statement in Election)", "bailable": True},
    "171H": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_5, "max_punishment": "Fine (Illegal Election Payments)", "bailable": True},
    "406": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_5, "max_punishment": "3 Years", "bailable": False},
    "408": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_5, "max_punishment": "7 Years", "bailable": False},
    "409": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_5, "max_punishment": "Life / 10 Years", "bailable": False},
    "420": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_5, "max_punishment": "7 Years", "bailable": False},
    "466": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_5, "max_punishment": "7 Years", "bailable": False},
    "467": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_5, "max_punishment": "Life / 10 Years", "bailable": False},
    "468": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_5, "max_punishment": "7 Years", "bailable": False},
    "471": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_5, "max_punishment": "7 Years / Same as Forgery", "bailable": False},
    "477A": {"is_heinous": True, "severity": "HEINOUS", "pillar": _PILLAR_5, "max_punishment": "7 Years", "bailable": True},
}


def normalize_code(code: str) -> str:
    """Upper-case and strip a Section code."""
    return (code or "").strip().upper()


def canonical_ipc_code(code: str) -> str:
    """Normalize variant IPC/Section notations (case, parentheses, Roman numerals) to canonical keys."""
    raw = normalize_code(code)
    if not raw:
        return ""
    # Normalize spaces around parentheses
    compact = raw.replace(" ", "")
    if compact in _VARIANT_MAP:
        return _VARIANT_MAP[compact]
    return raw


def explain(code: str):
    """Return the one-line explanation for a section code, or None."""
    canon = canonical_ipc_code(code)
    return EXPLANATIONS.get(canon) or EXPLANATIONS.get(normalize_code(code))


def classify_section(code: str) -> dict:
    """Classify an IPC section under the 5-pillar Heinous vs. Non-Heinous rubric."""
    raw = (code or "").strip()
    canon = canonical_ipc_code(raw)
    spec = HEINOUS_SPEC.get(canon) or HEINOUS_SPEC.get(normalize_code(raw))
    explanation = explain(raw) or ""
    if spec:
        return {
            "code": raw,
            "canonical_code": canon,
            "is_heinous": spec["is_heinous"],
            "severity": spec["severity"],
            "pillar": spec["pillar"],
            "max_punishment": spec["max_punishment"],
            "bailable": spec["bailable"],
            "explanation": explanation,
        }
    return {
        "code": raw,
        "canonical_code": canon,
        "is_heinous": False,
        "severity": "NON_HEINOUS",
        "pillar": "Non-Heinous: Minor / Protest / Regulatory",
        "max_punishment": "<= 2-3 Years / Fine",
        "bailable": True,
        "explanation": explanation,
    }
