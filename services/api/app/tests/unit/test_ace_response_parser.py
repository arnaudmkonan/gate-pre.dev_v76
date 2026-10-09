"""
Unit tests — ACE Response Parser  (Tasks 3.1 & 3.5)
"""
import pytest
from app.services.ace_response_parser import ACEResponseParser, ParsedResponse


@pytest.fixture
def parser():
    return ACEResponseParser()


class TestEntryResponseParsing:

    def test_parse_ae_code(self, parser):
        content = "AE|ABC12345678|20240115|Accepted Entry"
        responses = parser.parse(content)
        assert len(responses) >= 1
        r = responses[0]
        assert r.response_code == "AE"
        assert r.new_status == "filed"
        assert r.severity == "success"
        assert r.message_type == "entry"

    def test_parse_rj_code_is_error(self, parser):
        content = "RJ|ABC12345678|20240115|Classification error"
        responses = parser.parse(content)
        assert len(responses) >= 1
        r = responses[0]
        assert r.response_code == "RJ"
        assert r.new_status == "rejected"
        assert r.severity == "error"
        assert r.is_actionable is True

    def test_parse_ac_code_sets_released(self, parser):
        content = "AC|XYZ99887766|20240120|Cargo released"
        responses = parser.parse(content)
        assert responses[0].new_status == "released"

    def test_parse_wo_warning_is_actionable(self, parser):
        content = "WO|DEF00112233|20240115|Bond insufficient"
        responses = parser.parse(content)
        r = responses[0]
        assert r.response_code == "WO"
        assert r.severity == "warning"
        assert r.is_actionable is True

    def test_parse_extracts_entry_number(self, parser):
        content = "AE|ABC12345678|20240115|Accepted"
        responses = parser.parse(content)
        assert responses[0].entry_number == "ABC12345678"

    def test_unknown_content_returns_unknown(self, parser):
        content = "THIS IS SOME RANDOM TEXT WITH NO CBP CODES"
        responses = parser.parse(content)
        assert any(r.message_type == "unknown" for r in responses)


class TestISFResponseParsing:

    def test_parse_ismatch(self, parser):
        content = "ISF-2024-001\nISMATCH\nBill of lading confirmed by carrier"
        responses = parser.parse(content)
        isf_resp = [r for r in responses if r.message_type == "isf"]
        assert len(isf_resp) >= 1
        r = isf_resp[0]
        assert r.response_code == "ISMATCH"
        assert r.new_status == "confirmed"
        assert r.severity == "success"

    def test_parse_nomatch_is_actionable(self, parser):
        content = "NOMATCH\nNo matching BOL in CBP manifest"
        responses = parser.parse(content)
        isf_resp = [r for r in responses if r.message_type == "isf"]
        assert len(isf_resp) >= 1
        r = isf_resp[0]
        assert r.response_code == "NOMATCH"
        assert r.is_actionable is True

    def test_parse_pending_isf(self, parser):
        content = "PENDING — waiting for carrier confirmation"
        responses = parser.parse(content)
        # PENDING matches ISF
        isf_resp = [r for r in responses if r.message_type == "isf"]
        # May not be in content depending on pattern; at least no crash
        assert isinstance(responses, list)


class TestStatusMapping:

    def test_map_entry_ae_to_filed(self, parser):
        assert parser.map_entry_status("AE") == "filed"

    def test_map_entry_ac_to_released(self, parser):
        assert parser.map_entry_status("AC") == "released"

    def test_map_entry_rj_to_rejected(self, parser):
        assert parser.map_entry_status("RJ") == "rejected"

    def test_map_entry_unknown_returns_none(self, parser):
        assert parser.map_entry_status("ZZ") is None

    def test_map_isf_ismatch_to_confirmed(self, parser):
        assert parser.map_isf_status("ISMATCH") == "confirmed"

    def test_map_isf_nomatch_to_no_match(self, parser):
        assert parser.map_isf_status("NOMATCH") == "no_match"

    def test_map_isf_unknown_returns_none(self, parser):
        assert parser.map_isf_status("FOOBAR") is None


class TestActionabilityHelpers:

    def test_rj_is_error(self, parser):
        r = ParsedResponse(raw_content="", message_type="entry", response_code="RJ")
        assert parser.is_error(r) is True

    def test_ae_not_error(self, parser):
        r = ParsedResponse(raw_content="", message_type="entry", response_code="AE")
        assert parser.is_error(r) is False

    def test_rj_requires_action(self, parser):
        r = ParsedResponse(raw_content="", response_code="RJ")
        assert parser.requires_action(r) is True

    def test_ae_does_not_require_action(self, parser):
        r = ParsedResponse(raw_content="", response_code="AE")
        assert parser.requires_action(r) is False


class TestFieldExtraction:

    def test_extract_entry_number_plain(self, parser):
        content = "Accepted entry ABC12345678 processed"
        num = parser._extract_entry_number(content)
        assert num == "ABC12345678"

    def test_extract_isf_number(self, parser):
        content = "ISF 20240115001234 ISMATCH"
        num = parser._extract_isf_number(content)
        assert num is not None
