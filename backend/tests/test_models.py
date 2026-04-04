import pytest
from pydantic import ValidationError

from app.tools.models import (
    CPE,
    CVE,
    CVSSScore,
    SearchCPEInput,
    SearchCVEInput,
)
from tests.conftest import make_fake_cve, make_fake_cpe, FakeNvdlibCVE


class TestCVSSScore:
    def test_default_all_none(self) -> None:
        score = CVSSScore()
        assert score.version is None
        assert score.base_score is None
        assert score.severity is None

    def test_with_values(self) -> None:
        score = CVSSScore(version="V31", base_score=9.8, severity="CRITICAL")
        assert score.version == "V31"
        assert score.base_score == 9.8
        assert score.severity == "CRITICAL"


class TestCVEParseScore:
    def test_list_input(self) -> None:
        cve = make_fake_cve(score=["V31", 9.8, "CRITICAL"])
        validated = CVE.model_validate(cve, by_alias=True, from_attributes=True)
        assert validated.score.version == "V31"
        assert validated.score.base_score == 9.8
        assert validated.score.severity == "CRITICAL"

    def test_dict_input(self) -> None:
        cve = make_fake_cve()
        cve.score = {"version": "V40", "base_score": 8.0, "severity": "HIGH"}
        validated = CVE.model_validate(cve, by_alias=True, from_attributes=True)
        assert validated.score.version == "V40"
        assert validated.score.base_score == 8.0

    def test_fallback_on_unexpected_input(self) -> None:
        cve = make_fake_cve()
        cve.score = "not a valid score"
        validated = CVE.model_validate(cve, by_alias=True, from_attributes=True)
        assert validated.score.version is None
        assert validated.score.base_score is None
        assert validated.score.severity is None

    def test_none_score_list(self) -> None:
        cve = make_fake_cve(score=[None, None, None])
        validated = CVE.model_validate(cve, by_alias=True, from_attributes=True)
        assert validated.score.version is None
        assert validated.score.base_score is None
        assert validated.score.severity is None


class TestCVEModelValidate:
    def test_all_fields_present(self) -> None:
        cve = make_fake_cve()
        validated = CVE.model_validate(cve, by_alias=True, from_attributes=True)
        assert validated.id == "CVE-2023-44487"
        assert validated.source_identifier == "cve@mitre.org"
        assert validated.published == "2023-10-10T14:15:10.883"
        assert validated.last_modified == "2024-06-27T18:34:20.870"
        assert validated.vuln_status == "Analyzed"
        assert validated.url == "https://nvd.nist.gov/vuln/detail/CVE-2023-44487"
        assert len(validated.descriptions) == 1
        assert len(validated.weaknesses) == 1
        assert len(validated.references) == 1

    def test_missing_optional_fields(self) -> None:
        cve = FakeNvdlibCVE(
            id="CVE-2024-00001",
            published="2024-01-01T00:00:00.000",
            descriptions=[FakeNvdlibCVE(value="Test CVE", lang="en")],
            weaknesses=[],
            references=[],
        )
        validated = CVE.model_validate(cve, by_alias=True, from_attributes=True)
        assert validated.id == "CVE-2024-00001"
        assert validated.source_identifier is None
        assert validated.last_modified is None
        assert validated.vuln_status is None
        assert validated.url is None
        assert validated.score.version is None


class TestSearchCVEInput:
    def test_single_filter(self) -> None:
        inp = SearchCVEInput(cve_id="CVE-2023-44487")
        assert inp.cve_id == "CVE-2023-44487"
        assert inp.cpe_name is None

    def test_multiple_filters(self) -> None:
        inp = SearchCVEInput(keyword_search="buffer overflow", cvss_v3_severity="HIGH")
        assert inp.keyword_search == "buffer overflow"
        assert inp.cvss_v3_severity == "HIGH"

    def test_no_filters_raises(self) -> None:
        with pytest.raises(ValidationError, match="At least one search filter"):
            SearchCVEInput()

    def test_start_date_without_end_raises(self) -> None:
        with pytest.raises(
            ValidationError,
            match="pub_start_date and pub_end_date must be provided together",
        ):
            SearchCVEInput(pub_start_date="2023-01-01")

    def test_end_date_without_start_raises(self) -> None:
        with pytest.raises(
            ValidationError,
            match="pub_start_date and pub_end_date must be provided together",
        ):
            SearchCVEInput(pub_end_date="2023-12-31")

    def test_both_dates_valid(self) -> None:
        inp = SearchCVEInput(pub_start_date="2023-01-01", pub_end_date="2023-12-31")
        assert inp.pub_start_date == "2023-01-01"
        assert inp.pub_end_date == "2023-12-31"


class TestSearchCPEInput:
    def test_valid_input_lowercases(self) -> None:
        inp = SearchCPEInput(product="Curl", version="8.4.0")
        assert inp.product == "curl"
        assert inp.vendor == "*"

    def test_product_too_short(self) -> None:
        with pytest.raises(ValidationError, match="Product must be between"):
            SearchCPEInput(product="a", version="1.0.0")

    def test_version_not_semver(self) -> None:
        with pytest.raises(ValidationError, match="Version must be a valid semver"):
            SearchCPEInput(product="curl", version="latest")

    def test_custom_vendor(self) -> None:
        inp = SearchCPEInput(product="curl", version="8.4.0", vendor="Haxx")
        assert inp.vendor == "haxx"
