"""Extract importer/client profile fields from onboarding PDFs (POA, W-9, 5106, etc.)."""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)

EIN_PATTERN = re.compile(r"\b(\d{2}-\d{7})\b")
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_PATTERN = re.compile(
    r"(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b"
)
DUNS_PATTERN = re.compile(r"\b(\d{2}-\d{3}-\d{4}|\d{9})\b")
WEBSITE_PATTERN = re.compile(
    r"\b(?:https?://)?(?:www\.)?[a-z0-9][-a-z0-9.]+\.[a-z]{2,}(?:/[^\s]*)?",
    re.I,
)
US_ZIP_LINE = re.compile(
    r"([^\n,]+),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)\b"
)
PORT_PATTERN = re.compile(r"\b(\d{4})\b")  # CBP port codes — weak signal

CLIENT_TYPES = frozenset(
    {"corporation", "llc", "partnership", "sole_proprietor", "government", "non_profit", "other"}
)

LLM_SCHEMA_HINT = """
Return JSON only with these optional string fields (omit unknown):
name, legal_name, dba_name, client_type (one of: corporation, llc, partnership, sole_proprietor, government, non_profit, other),
ior_number, ein, duns, address_line_1, address_line_2, city, state_province, postal_code, country (2-letter),
phone, email, website, primary_port (4-digit CBP port if present), notes (short),
document_hint (poa|w9|5106|bond|other|unknown).
Use XX-XXXXXXX for EIN/IOR when found. Importer/grantor/importer of record is the client — not the customs broker.
"""


class ClientOnboardingExtractService:
    async def extract_from_pdf(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        from app.services.extractors.pdf_extractor import PDFExtractor

        extractor = PDFExtractor(enable_ocr=False)
        text = (await extractor.extract_text(file_bytes)).strip()
        warnings: List[str] = []

        if not text:
            return {
                "suggestions": {},
                "filled_fields": [],
                "method": "none",
                "document_hint": "unknown",
                "warnings": ["Could not read text from this PDF (try a text-based PDF or re-scan)."],
                "text_length": 0,
            }

        if len(text) < 80:
            warnings.append("Very little text extracted; suggestions may be incomplete.")

        from app.services.intake_profile_parser import (
            is_intake_registry_document,
            parse_intake_registry_entities,
        )

        if is_intake_registry_document(text):
            entities = parse_intake_registry_entities(text)
            if entities:
                primary = entities[0]
                warnings_list = list(warnings)
                if len(entities) > 1:
                    warnings_list.append(
                        f"Found {len(entities)} company profiles in this PDF; "
                        "select which one to use for the form."
                    )
                return {
                    "suggestions": primary["suggestions"],
                    "filled_fields": primary["filled_fields"],
                    "entities": [
                        {
                            "entity_id": e["entity_id"],
                            "display_name": e["display_name"],
                            "suggestions": e["suggestions"],
                            "filled_fields": e["filled_fields"],
                        }
                        for e in entities
                    ],
                    "entity_count": len(entities),
                    "method": "intake_registry",
                    "document_hint": "intake_registry",
                    "warnings": warnings_list,
                    "text_length": len(text),
                }

        heuristic, h_fields = self._heuristic_extract(text)
        llm_fields: Dict[str, Any] = {}
        method = "heuristic"

        if settings.openai_api_key and settings.openai_api_key.strip():
            try:
                llm_fields, doc_hint = await self._llm_extract(text, filename)
                method = "hybrid"
                merged, filled = self._merge_suggestions(heuristic, llm_fields)
                return {
                    "suggestions": merged,
                    "filled_fields": filled,
                    "method": method,
                    "document_hint": doc_hint or self._guess_document_hint(text),
                    "warnings": warnings,
                    "text_length": len(text),
                }
            except Exception as exc:
                logger.warning("LLM client extract failed, using heuristics: %s", exc)
                msg = str(exc).lower()
                if "insufficient_quota" in msg or "credit" in msg or "429" in msg:
                    warnings.append(
                        "OpenAI API key is set but the account has no credits or quota "
                        "(check billing at platform.openai.com). Using pattern matching only."
                    )
                elif "invalid_api_key" in msg or "incorrect api key" in msg:
                    warnings.append(
                        "OpenAI API key was rejected. Check OPENAI_API_KEY in .env and restart the API."
                    )
                else:
                    warnings.append(
                        f"AI extraction failed ({type(exc).__name__}); using pattern matching only."
                    )

        merged, filled = self._merge_suggestions(heuristic, {})
        if not filled:
            warnings.append("No client fields detected automatically — enter details manually.")
        elif not settings.openai_api_key or not settings.openai_api_key.strip():
            warnings.append(
                "OPENAI_API_KEY is not set in the API environment — only basic pattern matching was used."
            )

        return {
            "suggestions": merged,
            "filled_fields": filled,
            "method": method,
            "document_hint": self._guess_document_hint(text),
            "warnings": warnings,
            "text_length": len(text),
        }

    def _heuristic_extract(self, text: str) -> Tuple[Dict[str, Any], List[str]]:
        out: Dict[str, Any] = {}
        filled: List[str] = []

        eins = EIN_PATTERN.findall(text)
        if eins:
            out["ein"] = eins[0]
            filled.append("ein")
            if len(eins) > 1 and eins[1] != eins[0]:
                out["ior_number"] = eins[1]
                filled.append("ior_number")
            elif "ior" in text.lower() or "importer of record" in text.lower():
                out["ior_number"] = eins[0]
                filled.append("ior_number")

        emails = EMAIL_PATTERN.findall(text)
        if emails:
            out["email"] = emails[0].lower()
            filled.append("email")

        phones = [
            p for p in PHONE_PATTERN.findall(text)
            if "+" in p or "(" in p or len(re.sub(r"\D", "", p)) >= 10
        ]
        if phones:
            out["phone"] = phones[0]
            filled.append("phone")

        duns_matches = DUNS_PATTERN.findall(text)
        for d in duns_matches:
            digits = d.replace("-", "")
            if len(digits) != 9:
                continue
            if digits == (out.get("ein") or "").replace("-", ""):
                continue
            out["duns"] = digits
            filled.append("duns")
            break

        sites = WEBSITE_PATTERN.findall(text)
        for site in sites:
            if "@" not in site and "cbp.gov" not in site.lower():
                out["website"] = site if site.startswith("http") else f"https://{site}"
                filled.append("website")
                break

        for line in text.splitlines():
            m = US_ZIP_LINE.search(line)
            if m:
                city_part, state, zip_code = m.group(1).strip(), m.group(2), m.group(3)
                if len(city_part) > 2 and len(city_part) < 80:
                    out["city"] = city_part.split(",")[-1].strip() if "," in city_part else city_part
                    out["state_province"] = state
                    out["postal_code"] = zip_code
                    out["country"] = out.get("country") or "US"
                    for f in ("city", "state_province", "postal_code", "country"):
                        if f in out and f not in filled:
                            filled.append(f)
                break

        name = self._guess_company_name(text)
        if name:
            out["name"] = name
            filled.append("name")

        ctype = self._guess_client_type(text)
        if ctype:
            out["client_type"] = ctype
            filled.append("client_type")

        return out, filled

    def _guess_company_name(self, text: str) -> Optional[str]:
        for label in (
            r"(?:legal name|company name|business name|importer(?: name)?|grantor)\s*[:\-]\s*(.+)",
            r"(?:name of (?:company|corporation|importer))\s*[:\-]\s*(.+)",
        ):
            m = re.search(label, text, re.I)
            if m:
                candidate = m.group(1).strip().split("\n")[0][:500]
                if 2 < len(candidate) < 120:
                    return candidate
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for ln in lines[:15]:
            if re.search(r"\b(LLC|L\.L\.C\.|Inc\.|Corp\.|Corporation|Company)\b", ln, re.I):
                if len(ln) < 120 and not ln.lower().startswith("page "):
                    return ln
        return None

    def _guess_client_type(self, text: str) -> Optional[str]:
        lower = text.lower()
        if " limited liability" in lower or re.search(r"\bllc\b", lower):
            return "llc"
        if " corporation" in lower or re.search(r"\binc\.?\b", lower):
            return "corporation"
        if " partnership" in lower:
            return "partnership"
        if " sole propriet" in lower:
            return "sole_proprietor"
        return None

    def _guess_document_hint(self, text: str) -> str:
        lower = text.lower()
        if "power of attorney" in lower or re.search(r"\bpoa\b", lower):
            return "poa"
        if "form w-9" in lower or "w9" in lower:
            return "w9"
        if "5106" in lower or "importer id" in lower:
            return "5106"
        if "customs bond" in lower or "surety" in lower:
            return "bond"
        if "ingestion profiles" in lower or "intake registry" in lower:
            return "intake_registry"
        return "unknown"

    async def _llm_extract(self, text: str, filename: str) -> Tuple[Dict[str, Any], str]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        snippet = text[:14000]
        prompt = (
            f"You extract importer/client onboarding data for a US customs broker.\n"
            f"Filename: {filename}\n{LLM_SCHEMA_HINT}\n\nDocument text:\n{snippet}"
        )
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You output valid JSON only. No markdown.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
        doc_hint = str(data.pop("document_hint", "unknown") or "unknown")
        cleaned = self._sanitize_suggestions(data)
        return cleaned, doc_hint

    def _sanitize_suggestions(self, data: Dict[str, Any]) -> Dict[str, Any]:
        allowed = {
            "name", "legal_name", "dba_name", "client_type", "ior_number", "ein", "duns",
            "address_line_1", "address_line_2", "city", "state_province", "postal_code",
            "country", "phone", "email", "website", "primary_port", "internal_code", "notes",
            "c_tpat_member",
        }
        out: Dict[str, Any] = {}
        for key, val in data.items():
            if key not in allowed or val is None:
                continue
            if isinstance(val, str):
                val = val.strip()
                if not val:
                    continue
            if key == "client_type" and str(val).lower() not in CLIENT_TYPES:
                continue
            if key == "ein" and not EIN_PATTERN.fullmatch(str(val)):
                m = EIN_PATTERN.search(str(val))
                if m:
                    val = m.group(1)
                else:
                    continue
            if key == "ior_number":
                ior_ok = re.fullmatch(r"\d{2}-\d{7}\d{2,3}", str(val.replace(" ", "")))
                ein_ok = EIN_PATTERN.fullmatch(str(val))
                if not ior_ok and not ein_ok:
                    m = re.search(r"\d{2}-\d{7}\d{2,3}", str(val).replace(" ", ""))
                    if m:
                        val = m.group(0)
                    else:
                        m = EIN_PATTERN.search(str(val))
                        if m:
                            val = m.group(1)
                        else:
                            continue
            out[key] = val

        from app.services.client_field_normalization import normalize_client_payload

        return normalize_client_payload(out)

    def _merge_suggestions(
        self,
        heuristic: Dict[str, Any],
        llm: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], List[str]]:
        merged = {**heuristic, **llm}
        for key in ("ein", "ior_number"):
            if key in heuristic and key not in llm and heuristic[key]:
                merged[key] = heuristic[key]
        filled = [k for k, v in merged.items() if v not in (None, "", [])]
        return merged, filled
