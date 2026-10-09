"""
ACE Response Message Parser  (Task 3.1 / 3.5)

Parses CBP ACE (Automated Commercial Environment) response files received
via SFTP.  CBP sends X12-formatted response messages to the broker's SFTP
response folder after processing each submission.

Supported response types:
  Entry Summary (SE):
    AE  - Accepted / Entry Matched
    AP  - Accepted Pending (awaiting exam or payment)
    AC  - Accepted Complete (cleared)
    1C  - Conveyance not found
    WO  - Warning — correctable error
    RJ  - Rejected — must correct and refile

  ISF (IS):
    ISMATCH   - Bill of Lading matched; carrier confirmed
    NOMATCH   - No matching BOL found
    PENDING   - Awaiting carrier confirmation

The parser maps these codes to internal EntryStatus / ISFStatus values
so the platform can auto-advance state without manual ACE portal checks.
"""
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Response code → (internal_status, description, severity)
# ---------------------------------------------------------------------------
ENTRY_RESPONSE_MAP: Dict[str, Tuple[str, str, str]] = {
    "AE": ("filed",        "Accepted — entry matched in ACE",                 "success"),
    "AP": ("filed",        "Accepted Pending — awaiting exam or payment",      "info"),
    "AC": ("released",     "Accepted Complete — cargo cleared for release",    "success"),
    "1C": ("error",        "Conveyance not found in CBP manifest",             "error"),
    "WO": ("filed",        "Warning — accepted with correctable error",        "warning"),
    "RJ": ("rejected",     "Rejected — must correct and refile",               "error"),
    # Less common
    "ER": ("error",        "Transmission error",                               "error"),
    "CF": ("filed",        "Confirmed — duplicate accepted entry",             "info"),
}

ISF_RESPONSE_MAP: Dict[str, Tuple[str, str, str]] = {
    "ISMATCH":   ("confirmed",    "ISF matched — carrier BOL confirmed",        "success"),
    "NOMATCH":   ("no_match",     "ISF not matched — no BOL found in manifest", "warning"),
    "PENDING":   ("submitted",    "ISF accepted — awaiting carrier confirmation", "info"),
    "REJECTED":  ("rejected",     "ISF rejected by CBP",                        "error"),
}


@dataclass
class ParsedResponse:
    """Structured result of parsing one ACE response record."""

    # Source metadata
    raw_content: str
    parsed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Classification
    message_type: str = ""          # "entry" | "isf" | "unknown"
    response_code: str = ""         # e.g. "AE", "ISMATCH"

    # Linked identifiers (extracted from response text)
    entry_number: Optional[str] = None
    isf_number: Optional[str] = None
    transaction_number: Optional[str] = None

    # Resolved status
    new_status: Optional[str] = None        # e.g. "filed", "released"
    status_description: str = ""
    severity: str = "info"                  # "success" | "info" | "warning" | "error"

    # Errors and warnings returned by CBP
    cbp_messages: List[str] = field(default_factory=list)
    is_actionable: bool = False             # True if broker must do something


class ACEResponseParser:
    """
    Parses raw ACE SFTP response files into structured ParsedResponse objects.

    Typical ACE response file structure (simplified X12):

        ISA*00*          *00*          *ZZ*CBPFILER       *ZZ*USNBP          *240115*0830*:*00801*000000001*0*P*>~
        GS*AG*FILER*CBPFILER*20240115*0830*1*X*008010~
        ST*997*0001~
        AK1*SE*1~
        AK9*A*1*1*1~
        SE*3*0001~
        GE*1*1~
        IEA*1*000000001~

    Or for Entry responses (proprietary CBP format):
        AE|ENTRY-2024-001|20240115|Accepted
    """

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def parse(self, raw_content: str) -> List[ParsedResponse]:
        """
        Parse a raw ACE response file.

        Handles multi-record files (one response per entry/ISF).
        Returns a list of ParsedResponse objects.
        """
        results = []

        # Attempt ISF response first (distinct keyword patterns)
        if any(k in raw_content.upper() for k in ("ISMATCH", "NOMATCH")):
            results.extend(self._parse_isf_responses(raw_content))

        # Then handle entry responses
        entry_responses = self._parse_entry_responses(raw_content)
        results.extend(entry_responses)

        if not results:
            # Fallback: return a single "unknown" record
            results.append(ParsedResponse(
                raw_content=raw_content,
                message_type="unknown",
                response_code="UNKNOWN",
                status_description="Unrecognised CBP response format",
                severity="warning",
            ))

        return results

    def parse_entry_response(self, raw_content: str) -> ParsedResponse:
        """
        Parse a single entry response record.  Convenience method.
        """
        results = self._parse_entry_responses(raw_content)
        return results[0] if results else ParsedResponse(
            raw_content=raw_content,
            message_type="unknown",
        )

    def parse_isf_response(self, raw_content: str) -> ParsedResponse:
        """
        Parse a single ISF response record.  Convenience method.
        """
        results = self._parse_isf_responses(raw_content)
        return results[0] if results else ParsedResponse(
            raw_content=raw_content,
            message_type="unknown",
        )

    # ------------------------------------------------------------------
    # Status mapping
    # ------------------------------------------------------------------

    def map_entry_status(self, response_code: str) -> Optional[str]:
        """Map ACE response code to internal entry status string."""
        mapping = ENTRY_RESPONSE_MAP.get(response_code.upper())
        return mapping[0] if mapping else None

    def map_isf_status(self, response_code: str) -> Optional[str]:
        """Map ACE ISF response code to internal ISF status string."""
        mapping = ISF_RESPONSE_MAP.get(response_code.upper())
        return mapping[0] if mapping else None

    def is_error(self, response: ParsedResponse) -> bool:
        """Return True if the response indicates filing was rejected."""
        return response.response_code.upper() in ("RJ", "ER", "REJECTED")

    def requires_action(self, response: ParsedResponse) -> bool:
        """Return True if the broker must take corrective action."""
        return response.response_code.upper() in ("RJ", "ER", "WO", "NOMATCH", "1C")

    # ------------------------------------------------------------------
    # Private parsers
    # ------------------------------------------------------------------

    def _parse_entry_responses(self, content: str) -> List[ParsedResponse]:
        """Parse entry summary (SE message type) responses."""
        results = []

        # Pattern 1: pipe-delimited format
        # AE|ENTRY-2024-001|20240115|Accepted
        pipe_pattern = re.compile(
            r'^(AE|AP|AC|1C|WO|RJ|ER|CF)\|([^\|]+)\|([^\|]*)\|([^\n\r]*)',
            re.MULTILINE | re.IGNORECASE,
        )
        for m in pipe_pattern.finditer(content):
            code = m.group(1).upper()
            entry_num = m.group(2).strip()
            cbp_msg = m.group(4).strip()
            mapping = ENTRY_RESPONSE_MAP.get(code, ("unknown", "Unknown response", "info"))
            resp = ParsedResponse(
                raw_content=content,
                message_type="entry",
                response_code=code,
                entry_number=entry_num,
                new_status=mapping[0],
                status_description=mapping[1],
                severity=mapping[2],
                cbp_messages=[cbp_msg] if cbp_msg else [],
                is_actionable=code in ("RJ", "ER", "WO", "1C"),
            )
            results.append(resp)

        # Pattern 2: keyword anywhere in content
        if not results:
            for code in ENTRY_RESPONSE_MAP:
                if re.search(rf'\b{code}\b', content, re.IGNORECASE):
                    mapping = ENTRY_RESPONSE_MAP[code]
                    entry_num = self._extract_entry_number(content)
                    results.append(ParsedResponse(
                        raw_content=content,
                        message_type="entry",
                        response_code=code,
                        entry_number=entry_num,
                        new_status=mapping[0],
                        status_description=mapping[1],
                        severity=mapping[2],
                        is_actionable=code in ("RJ", "ER", "WO", "1C"),
                    ))
                    break  # Take first matched code

        return results

    def _parse_isf_responses(self, content: str) -> List[ParsedResponse]:
        """Parse ISF (IS message type) responses."""
        results = []
        upper = content.upper()

        for code, mapping in ISF_RESPONSE_MAP.items():
            if code in upper:
                isf_num = self._extract_isf_number(content)
                results.append(ParsedResponse(
                    raw_content=content,
                    message_type="isf",
                    response_code=code,
                    isf_number=isf_num,
                    new_status=mapping[0],
                    status_description=mapping[1],
                    severity=mapping[2],
                    is_actionable=code in ("NOMATCH", "REJECTED"),
                ))

        return results

    # ------------------------------------------------------------------
    # Field extractors
    # ------------------------------------------------------------------

    def _extract_entry_number(self, content: str) -> Optional[str]:
        """Attempt to extract an entry number from raw content."""
        # Common format: 3-char filer + 8-digit seq number
        m = re.search(r'\b([A-Z]{3}\d{8})\b', content)
        if m:
            return m.group(1)
        # Hyphenated format: FILER-YEAR-SEQ
        m = re.search(r'\b([A-Z]{3}[-]\d{4}[-]\d+)\b', content)
        if m:
            return m.group(1)
        return None

    def _extract_isf_number(self, content: str) -> Optional[str]:
        """Attempt to extract an ISF number from raw content."""
        # ISF numbers are often prefixed with "ISF" or are 16-digit
        m = re.search(r'ISF[-\s]?(\d{6,})', content, re.IGNORECASE)
        if m:
            return m.group(0)
        m = re.search(r'\b(\d{16})\b', content)
        if m:
            return m.group(1)
        return None
