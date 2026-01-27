"""
Entry Validation Service.

Comprehensive validation rules engine for customs entries.

Task 1.6 from ROADMAP_FULL_WORKFLOW.md
"""
import re
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal


class ValidationSeverity(str, Enum):
    """Validation message severity levels."""
    ERROR = "error"       # Must be fixed before filing
    WARNING = "warning"   # Should be reviewed
    INFO = "info"         # Informational


@dataclass
class ValidationMessage:
    """A validation message for a specific field."""
    field: str
    message: str
    severity: ValidationSeverity
    code: str  # Unique code for the validation rule
    suggestion: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "message": self.message,
            "severity": self.severity.value,
            "code": self.code,
            "suggestion": self.suggestion,
        }


@dataclass
class ValidationResult:
    """Complete validation result for an entry."""
    valid: bool
    filing_ready: bool  # No errors, entry can be filed
    errors: List[ValidationMessage] = field(default_factory=list)
    warnings: List[ValidationMessage] = field(default_factory=list)
    info: List[ValidationMessage] = field(default_factory=list)
    summary: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "filing_ready": self.filing_ready,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "info": [i.to_dict() for i in self.info],
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "summary": self.summary,
        }


class EntryValidationService:
    """
    Comprehensive validation service for customs entries.
    
    Validates:
    - Required fields (CBP mandatory fields)
    - HTS code format and validity
    - Value reasonableness
    - Party information
    - Country of origin consistency
    - ADD/CVD applicability
    - Entry type requirements
    """
    
    # CBP Required fields for consumption entries
    REQUIRED_HEADER_FIELDS = {
        "port_of_entry": "Port of Entry",
        "entry_type": "Entry Type",
        "importer_of_record_number": "Importer of Record Number",
    }
    
    RECOMMENDED_HEADER_FIELDS = {
        "entry_date": "Entry Date",
        "bill_of_lading": "Bill of Lading",
        "mode_of_transport": "Mode of Transport",
        "carrier_code": "Carrier Code",
    }
    
    # HTS code patterns
    HTS_PATTERN = re.compile(r"^\d{4}\.\d{2}(\.\d{2})?(\.\d{2})?$")
    HTS_CHAPTER_PATTERN = re.compile(r"^\d{2}")
    
    # Known ADD/CVD countries/products (sample - would come from database)
    ADD_CVD_WATCH_COUNTRIES = {"CN", "VN", "KR", "IN", "TW", "TH"}
    ADD_CVD_WATCH_CHAPTERS = {
        "72": "Steel",
        "73": "Steel articles",
        "76": "Aluminum",
        "84": "Machinery (check solar panels)",
        "85": "Electrical (check solar panels)",
        "94": "Furniture",
    }
    
    # Section 301 countries
    SECTION_301_COUNTRIES = {"CN"}
    
    # Valid port codes (sample - 4 digit codes)
    PORT_CODE_PATTERN = re.compile(r"^\d{4}$")
    
    # Valid IOR number patterns
    IOR_PATTERNS = [
        re.compile(r"^\d{2}-\d{7}$"),  # EIN format
        re.compile(r"^\d{9}$"),        # 9-digit
        re.compile(r"^[A-Z]{2}\d{7}$"),  # CBP assigned
    ]
    
    def __init__(self, entry: Any, lines: List[Any] = None, parties: List[Any] = None):
        """
        Initialize validator with entry and related data.
        
        Args:
            entry: The Entry model instance
            lines: List of EntryLine instances
            parties: List of EntryParty instances
        """
        self.entry = entry
        self.lines = lines or []
        self.parties = parties or []
        self.errors: List[ValidationMessage] = []
        self.warnings: List[ValidationMessage] = []
        self.info: List[ValidationMessage] = []
    
    def validate(self) -> ValidationResult:
        """
        Run all validation checks and return result.
        """
        # Clear previous results
        self.errors = []
        self.warnings = []
        self.info = []
        
        # Run validation checks
        self._validate_required_fields()
        self._validate_entry_type()
        self._validate_port_of_entry()
        self._validate_importer()
        self._validate_transport()
        self._validate_lines()
        self._validate_values()
        self._validate_parties()
        self._check_add_cvd_applicability()
        self._check_section_301_applicability()
        self._validate_totals()
        
        # Generate summary
        valid = len(self.errors) == 0
        filing_ready = valid and len([w for w in self.warnings if "critical" in w.code.lower()]) == 0
        
        if valid:
            summary = f"Entry is valid with {len(self.warnings)} warning(s)"
        else:
            summary = f"Entry has {len(self.errors)} error(s) that must be fixed"
        
        return ValidationResult(
            valid=valid,
            filing_ready=filing_ready,
            errors=self.errors,
            warnings=self.warnings,
            info=self.info,
            summary=summary,
        )
    
    def _add_error(self, field: str, message: str, code: str, suggestion: str = None):
        """Add an error message."""
        self.errors.append(ValidationMessage(
            field=field,
            message=message,
            severity=ValidationSeverity.ERROR,
            code=code,
            suggestion=suggestion,
        ))
    
    def _add_warning(self, field: str, message: str, code: str, suggestion: str = None):
        """Add a warning message."""
        self.warnings.append(ValidationMessage(
            field=field,
            message=message,
            severity=ValidationSeverity.WARNING,
            code=code,
            suggestion=suggestion,
        ))
    
    def _add_info(self, field: str, message: str, code: str, suggestion: str = None):
        """Add an info message."""
        self.info.append(ValidationMessage(
            field=field,
            message=message,
            severity=ValidationSeverity.INFO,
            code=code,
            suggestion=suggestion,
        ))
    
    def _validate_required_fields(self):
        """Validate CBP mandatory header fields."""
        for field_name, label in self.REQUIRED_HEADER_FIELDS.items():
            value = getattr(self.entry, field_name, None)
            if not value:
                self._add_error(
                    field=field_name,
                    message=f"{label} is required for CBP filing",
                    code="REQUIRED_FIELD_MISSING",
                    suggestion=f"Enter a valid {label.lower()}"
                )
        
        for field_name, label in self.RECOMMENDED_HEADER_FIELDS.items():
            value = getattr(self.entry, field_name, None)
            if not value:
                self._add_warning(
                    field=field_name,
                    message=f"{label} is recommended for complete entry",
                    code="RECOMMENDED_FIELD_MISSING",
                )
    
    def _validate_entry_type(self):
        """Validate entry type and type-specific requirements."""
        entry_type = getattr(self.entry, 'entry_type', None)
        
        valid_types = ["01", "02", "03", "05", "06", "07", "09", "22", "23", "24"]
        if entry_type and entry_type not in valid_types:
            self._add_error(
                field="entry_type",
                message=f"Invalid entry type: {entry_type}",
                code="INVALID_ENTRY_TYPE",
                suggestion="Use a valid CBP entry type (01, 02, 03, etc.)"
            )
        
        # Type-specific validations
        if entry_type == "06":  # Warehouse entry
            bond_type = getattr(self.entry, 'bond_type', None)
            if not bond_type or bond_type not in ["8", "9"]:
                self._add_warning(
                    field="bond_type",
                    message="Warehouse entries typically require bond type 8 or 9",
                    code="WAREHOUSE_BOND_CHECK",
                )
    
    def _validate_port_of_entry(self):
        """Validate port of entry format."""
        port = getattr(self.entry, 'port_of_entry', None)
        if port:
            if not self.PORT_CODE_PATTERN.match(port):
                self._add_error(
                    field="port_of_entry",
                    message=f"Invalid port code format: {port}",
                    code="INVALID_PORT_FORMAT",
                    suggestion="Port code should be 4 digits (e.g., 2704)"
                )
    
    def _validate_importer(self):
        """Validate importer of record information."""
        ior_number = getattr(self.entry, 'importer_of_record_number', None)
        ior_name = getattr(self.entry, 'importer_of_record_name', None)
        
        if not ior_number and not ior_name:
            self._add_error(
                field="importer_of_record",
                message="Importer of record information is required",
                code="IOR_REQUIRED",
            )
        
        if ior_number:
            # Validate IOR number format
            valid_format = any(p.match(ior_number) for p in self.IOR_PATTERNS)
            if not valid_format:
                self._add_warning(
                    field="importer_of_record_number",
                    message=f"IOR number format may be invalid: {ior_number}",
                    code="IOR_FORMAT_WARNING",
                    suggestion="Expected format: XX-XXXXXXX (EIN) or 9 digits"
                )
    
    def _validate_transport(self):
        """Validate transport information."""
        mode = getattr(self.entry, 'mode_of_transport', None)
        
        valid_modes = ["10", "11", "12", "20", "21", "30", "31", "32", "33", "34", "40", "41"]
        if mode and mode not in valid_modes:
            self._add_warning(
                field="mode_of_transport",
                message=f"Unknown mode of transport: {mode}",
                code="UNKNOWN_TRANSPORT_MODE",
            )
        
        # Vessel-specific checks
        if mode and mode.startswith("1"):  # Vessel
            vessel = getattr(self.entry, 'vessel_name', None)
            if not vessel:
                self._add_info(
                    field="vessel_name",
                    message="Vessel name recommended for ocean shipments",
                    code="VESSEL_NAME_RECOMMENDED",
                )
    
    def _validate_lines(self):
        """Validate line items."""
        if not self.lines:
            self._add_error(
                field="lines",
                message="At least one line item is required",
                code="NO_LINE_ITEMS",
            )
            return
        
        seen_line_numbers = set()
        
        for line in self.lines:
            line_num = getattr(line, 'line_number', 0)
            prefix = f"lines[{line_num}]"
            
            # Check for duplicate line numbers
            if line_num in seen_line_numbers:
                self._add_error(
                    field=f"{prefix}.line_number",
                    message=f"Duplicate line number: {line_num}",
                    code="DUPLICATE_LINE_NUMBER",
                )
            seen_line_numbers.add(line_num)
            
            # Validate HTS code
            hts = getattr(line, 'hts_code', None)
            if not hts:
                self._add_error(
                    field=f"{prefix}.hts_code",
                    message=f"Line {line_num}: HTS code is required",
                    code="HTS_REQUIRED",
                )
            else:
                self._validate_hts_code(hts, prefix, line_num)
            
            # Validate country of origin
            country = getattr(line, 'country_of_origin', None)
            if not country:
                self._add_warning(
                    field=f"{prefix}.country_of_origin",
                    message=f"Line {line_num}: Country of origin recommended",
                    code="COUNTRY_RECOMMENDED",
                )
            elif len(country) != 2:
                self._add_error(
                    field=f"{prefix}.country_of_origin",
                    message=f"Line {line_num}: Country code must be 2 letters (ISO 3166)",
                    code="INVALID_COUNTRY_FORMAT",
                )
            
            # Validate entered value
            value = getattr(line, 'entered_value', None)
            if not value or float(value) <= 0:
                self._add_error(
                    field=f"{prefix}.entered_value",
                    message=f"Line {line_num}: Positive entered value is required",
                    code="VALUE_REQUIRED",
                )
            
            # Validate quantity
            qty = getattr(line, 'quantity_1', None)
            if not qty or float(qty) <= 0:
                self._add_warning(
                    field=f"{prefix}.quantity_1",
                    message=f"Line {line_num}: Quantity should be specified",
                    code="QUANTITY_RECOMMENDED",
                )
    
    def _validate_hts_code(self, hts: str, prefix: str, line_num: int):
        """Validate HTS code format."""
        # Remove any extra dots or spaces
        hts_clean = hts.strip().replace(" ", "")
        
        # Check format
        if not self.HTS_PATTERN.match(hts_clean):
            self._add_error(
                field=f"{prefix}.hts_code",
                message=f"Line {line_num}: Invalid HTS format '{hts}'",
                code="INVALID_HTS_FORMAT",
                suggestion="HTS format: XXXX.XX or XXXX.XX.XX or XXXX.XX.XX.XX"
            )
            return
        
        # Extract chapter
        chapter = hts_clean[:2]
        
        # Check for valid chapter range (01-99)
        try:
            ch_num = int(chapter)
            if ch_num < 1 or ch_num > 99:
                self._add_error(
                    field=f"{prefix}.hts_code",
                    message=f"Line {line_num}: Invalid HTS chapter {chapter}",
                    code="INVALID_HTS_CHAPTER",
                )
        except ValueError:
            self._add_error(
                field=f"{prefix}.hts_code",
                message=f"Line {line_num}: Cannot parse HTS chapter",
                code="HTS_PARSE_ERROR",
            )
        
        # Check minimum 6 digits for filing
        if len(hts_clean.replace(".", "")) < 6:
            self._add_warning(
                field=f"{prefix}.hts_code",
                message=f"Line {line_num}: HTS code should have at least 6 digits for filing",
                code="HTS_LENGTH_WARNING",
            )
    
    def _validate_values(self):
        """Validate entry values and reasonableness checks."""
        total_value = sum(
            float(getattr(line, 'entered_value', 0) or 0)
            for line in self.lines
        )
        
        # Large value warning
        if total_value > 1000000:
            self._add_info(
                field="total_entered_value",
                message=f"High-value entry (${total_value:,.2f}). Review for accuracy.",
                code="HIGH_VALUE_ENTRY",
            )
        
        # Check for zero value lines
        for line in self.lines:
            line_num = getattr(line, 'line_number', 0)
            value = float(getattr(line, 'entered_value', 0) or 0)
            qty = float(getattr(line, 'quantity_1', 1) or 1)
            
            if qty > 0:
                unit_value = value / qty
                
                # Very low unit value warning
                if unit_value < 0.01:
                    self._add_warning(
                        field=f"lines[{line_num}].entered_value",
                        message=f"Line {line_num}: Very low unit value (${unit_value:.4f}). Verify.",
                        code="LOW_UNIT_VALUE_WARNING",
                    )
                
                # Very high unit value warning
                if unit_value > 100000:
                    self._add_info(
                        field=f"lines[{line_num}].entered_value",
                        message=f"Line {line_num}: High unit value (${unit_value:,.2f}). Review.",
                        code="HIGH_UNIT_VALUE_INFO",
                    )
    
    def _validate_parties(self):
        """Validate party information."""
        # Check for required party types if relevant
        has_manufacturer = False
        has_seller = False
        
        for party in self.parties:
            role = getattr(party, 'role', '')
            if role == 'manufacturer':
                has_manufacturer = True
            elif role == 'seller':
                has_seller = True
        
        # For certain entry types, parties may be required
        # This is informational for now
        if self.lines and not has_manufacturer:
            self._add_info(
                field="parties",
                message="Manufacturer information recommended for complete entry",
                code="MANUFACTURER_RECOMMENDED",
            )
    
    def _check_add_cvd_applicability(self):
        """Check if ADD/CVD orders may apply."""
        for line in self.lines:
            line_num = getattr(line, 'line_number', 0)
            hts = getattr(line, 'hts_code', '') or ''
            country = getattr(line, 'country_of_origin', '') or ''
            
            if not hts or not country:
                continue
            
            # Check if country is on watch list
            if country.upper() in self.ADD_CVD_WATCH_COUNTRIES:
                # Check HTS chapter
                chapter = hts[:2] if len(hts) >= 2 else ''
                if chapter in self.ADD_CVD_WATCH_CHAPTERS:
                    product_type = self.ADD_CVD_WATCH_CHAPTERS[chapter]
                    self._add_warning(
                        field=f"lines[{line_num}]",
                        message=f"Line {line_num}: Potential ADD/CVD applicability for {product_type} from {country}",
                        code="ADD_CVD_CHECK_REQUIRED",
                        suggestion="Verify if ADD/CVD orders apply to this HTS/country combination"
                    )
    
    def _check_section_301_applicability(self):
        """Check if Section 301 tariffs may apply."""
        china_lines = []
        
        for line in self.lines:
            country = getattr(line, 'country_of_origin', '') or ''
            if country.upper() in self.SECTION_301_COUNTRIES:
                china_lines.append(getattr(line, 'line_number', 0))
        
        if china_lines:
            self._add_info(
                field="lines",
                message=f"Lines {china_lines} may be subject to Section 301 tariffs (China origin)",
                code="SECTION_301_CHECK",
                suggestion="Verify Section 301 list applicability during duty calculation"
            )
    
    def _validate_totals(self):
        """Validate entry totals consistency."""
        calculated_value = sum(
            float(getattr(line, 'entered_value', 0) or 0)
            for line in self.lines
        )
        
        stored_value = float(getattr(self.entry, 'total_entered_value', 0) or 0)
        
        # Check if totals need recalculation
        if abs(calculated_value - stored_value) > 0.01:
            self._add_warning(
                field="total_entered_value",
                message=f"Total value ({stored_value:,.2f}) differs from sum of lines ({calculated_value:,.2f})",
                code="TOTAL_MISMATCH",
                suggestion="Recalculate entry totals"
            )
        
        # Check line count
        actual_count = len(self.lines)
        stored_count = getattr(self.entry, 'line_count', 0)
        
        if actual_count != stored_count:
            self._add_info(
                field="line_count",
                message=f"Line count ({stored_count}) differs from actual ({actual_count})",
                code="LINE_COUNT_MISMATCH",
            )
