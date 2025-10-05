import re
from typing import Dict, Iterable, Optional

try:
    import pdfplumber  # type: ignore
except Exception:
    pdfplumber = None

try:
    import pytesseract  # type: ignore
except Exception:
    pytesseract = None

try:
    import pypdfium2 as pdfium  # type: ignore
except Exception:
    pdfium = None


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


def _extract_text_pdfplumber(pdf_bytes: bytes) -> str:
    if not pdfplumber:
        return ""
    from io import BytesIO

    text = ""
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text += (page.extract_text() or "") + "\n"
    return text


def _extract_text_ocr(pdf_bytes: bytes, languages: Optional[Iterable[str]] = None) -> str:
    """
    Fallback: rasterizér PDF-sider og kør OCR med Tesseract.
    languages: fx ["dan","eng"] hvis dansk sprogdata er installeret.
    """
    if not (pdfium and pytesseract):
        return ""

    langs = "+".join(languages) if languages else None
    doc = pdfium.PdfDocument(pdf_bytes)
    text_parts = []
    # 150 DPI er ofte nok; bump evt. til 200 hvis dine scans er små.
    for i in range(len(doc)):
        page = doc.get_page(i)
        bitmap = page.render(scale=150 / 72).to_pil()  # 72 DPI → 150 DPI
        try:
            txt = pytesseract.image_to_string(bitmap, lang=langs) if langs else pytesseract.image_to_string(bitmap)
        except Exception:
            txt = pytesseract.image_to_string(bitmap)
        text_parts.append(txt or "")
        page.close()
    return "\n".join(text_parts)


def parse_scores_from_text(text: str) -> Dict[str, float]:
    out: Dict[str, float] = {
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


def parse_scores_from_pdf_bytes(pdf_bytes: bytes) -> Dict[str, float]:
    """
    Prøv først direkte tekst; hvis tomt, falder vi tilbage til OCR.
    Forsøger dansk+engelsk OCR, men fortsætter hvis sprogdata mangler.
    """
    # 1) Direkte tekst
    text = _extract_text_pdfplumber(pdf_bytes) or ""
    # 2) OCR fallback, hvis ikke noget tekst
    if not text.strip():
        # prøv dansk+engelsk, men hvis sprogdata ikke findes fortsætter pytesseract alligevel
        text = _extract_text_ocr(pdf_bytes, languages=["dan", "eng"]) or ""

    return parse_scores_from_text(text)
