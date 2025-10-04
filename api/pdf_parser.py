# api/pdf_parser.py
import re


DOMAIN_ALIASES = {
    "sprogforståelse": [r"sprogforst[åa]else"],
    "ordforråd": [r"ordforr[åa]d"],
    "kommunikativeStrategier": [r"kommunikative\s*strategier?"],
    "rim": [r"rim"],
    "opmærksomhedPåSkrift": [r"opm[æa]rksomhed\s*p[åa]\s*skrift"],
}

NUM = r"(?P<num>\d{1,3}(?:[.,]\d{1,2})?)"

def _norm_num(s: str) -> float:
    s = s.strip().replace(",", ".")
    return float(s)

def parse_scores_from_text(text: str) -> dict[str, float]:
    out: dict[str, float] = {
        "sprogforståelse": 0.0,
        "ordforråd": 0.0,
        "kommunikativeStrategier": 0.0,
        "rim": 0.0,
        "opmærksomhedPåSkrift": 0.0,
    }
    t = " ".join(text.split())

    for dom, pats in DOMAIN_ALIASES.items():
        found = False
        for p in pats:
            regex = re.compile(rf"{p}[^0-9]{{0,40}}{NUM}", re.IGNORECASE)
            m = regex.search(t)
            if m:
                out[dom] = _norm_num(m.group("num"))
                found = True
                break
        if not found:
            for p in pats:
                regex = re.compile(rf"{p}\s*{NUM}\s*(?:point|pts?)?", re.IGNORECASE)
                m = regex.search(t)
                if m:
                    out[dom] = _norm_num(m.group("num"))
                    break

    return out
