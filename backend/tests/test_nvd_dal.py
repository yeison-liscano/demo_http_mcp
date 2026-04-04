from unittest.mock import MagicMock

import nvdlib
from http_mcp.types import Arguments
from pymocks import Mock, with_mock

from app.tools.nvd_dal import search_cpe, search_cve
from tests.conftest import (
    SearchCPECapture,
    SearchCVECapture,
    make_fake_cpe,
    make_fake_cve,
)


def _make_arguments(inputs: object) -> Arguments:
    """Create an Arguments object with a dummy request."""
    request = MagicMock()
    return Arguments(request=request, inputs=inputs)


class TestSearchCVE:
    async def test_cve_id_maps_to_cveId(
        self,
        fake_search_cve: SearchCVECapture,
        mock_search_cve: Mock,
    ) -> None:
        from app.tools.models import SearchCVEInput

        args = _make_arguments(SearchCVEInput(cve_id="CVE-2023-44487"))
        async with with_mock(mock_search_cve):
            result = await search_cve(args)
        assert "cveId" in fake_search_cve.captured_kwargs
        assert fake_search_cve.captured_kwargs["cveId"] == "CVE-2023-44487"
        assert len(result.cves) == 1
        assert result.cves[0].id == "CVE-2023-44487"

    async def test_multiple_filters_mapped(
        self,
        fake_search_cve: SearchCVECapture,
        mock_search_cve: Mock,
    ) -> None:
        from app.tools.models import SearchCVEInput

        args = _make_arguments(
            SearchCVEInput(
                keyword_search="buffer overflow",
                cvss_v3_severity="HIGH",
                no_rejected=True,
            ),
        )
        async with with_mock(mock_search_cve):
            await search_cve(args)
        assert fake_search_cve.captured_kwargs["keywordSearch"] == "buffer overflow"
        assert fake_search_cve.captured_kwargs["cvssV3Severity"] == "HIGH"
        assert fake_search_cve.captured_kwargs["noRejected"] is True

    async def test_none_fields_excluded(
        self,
        fake_search_cve: SearchCVECapture,
        mock_search_cve: Mock,
    ) -> None:
        from app.tools.models import SearchCVEInput

        args = _make_arguments(SearchCVEInput(cve_id="CVE-2023-44487"))
        async with with_mock(mock_search_cve):
            await search_cve(args)
        assert "cpeName" not in fake_search_cve.captured_kwargs
        assert "keywordSearch" not in fake_search_cve.captured_kwargs
        assert "cweId" not in fake_search_cve.captured_kwargs

    async def test_false_boolean_flags_excluded(
        self,
        fake_search_cve: SearchCVECapture,
        mock_search_cve: Mock,
    ) -> None:
        from app.tools.models import SearchCVEInput

        args = _make_arguments(
            SearchCVEInput(cve_id="CVE-2023-44487", has_kev=False, no_rejected=False),
        )
        async with with_mock(mock_search_cve):
            await search_cve(args)
        assert "hasKev" not in fake_search_cve.captured_kwargs
        assert "noRejected" not in fake_search_cve.captured_kwargs

    async def test_true_boolean_flags_included(
        self,
        fake_search_cve: SearchCVECapture,
        mock_search_cve: Mock,
    ) -> None:
        from app.tools.models import SearchCVEInput

        args = _make_arguments(
            SearchCVEInput(cve_id="CVE-2023-44487", has_kev=True),
        )
        async with with_mock(mock_search_cve):
            await search_cve(args)
        assert fake_search_cve.captured_kwargs["hasKev"] is True

    async def test_results_validated_into_pydantic_models(
        self,
        fake_search_cve: SearchCVECapture,
        mock_search_cve: Mock,
    ) -> None:
        from app.tools.models import CVE, CVSSScore, SearchCVEInput

        args = _make_arguments(SearchCVEInput(cve_id="CVE-2023-44487"))
        async with with_mock(mock_search_cve):
            result = await search_cve(args)
        cve = result.cves[0]
        assert isinstance(cve, CVE)
        assert isinstance(cve.score, CVSSScore)
        assert cve.score.version == "V31"
        assert cve.score.base_score == 7.5
        assert cve.score.severity == "HIGH"


class TestSearchCPE:
    def test_cpe_match_string_format(
        self,
        fake_search_cpe: SearchCPECapture,
        mock_search_cpe: Mock,
    ) -> None:
        from app.tools.models import SearchCPEInput

        args = _make_arguments(SearchCPEInput(product="curl", version="8.4.0", vendor="haxx"))
        with with_mock(mock_search_cpe):
            result = search_cpe(args)
        assert fake_search_cpe.captured_kwargs["cpeMatchString"] == "cpe:2.3:a:haxx:curl:8.4.0"

    def test_default_vendor_wildcard(
        self,
        fake_search_cpe: SearchCPECapture,
        mock_search_cpe: Mock,
    ) -> None:
        from app.tools.models import SearchCPEInput

        args = _make_arguments(SearchCPEInput(product="curl", version="8.4.0"))
        with with_mock(mock_search_cpe):
            search_cpe(args)
        assert "cpe:2.3:a:*:curl:8.4.0" == fake_search_cpe.captured_kwargs["cpeMatchString"]

    def test_results_validated_into_pydantic_models(
        self,
        fake_search_cpe: SearchCPECapture,
        mock_search_cpe: Mock,
    ) -> None:
        from app.tools.models import CPE, SearchCPEInput

        args = _make_arguments(SearchCPEInput(product="curl", version="8.4.0"))
        with with_mock(mock_search_cpe):
            result = search_cpe(args)
        assert len(result.cpes) == 1
        cpe = result.cpes[0]
        assert isinstance(cpe, CPE)
        assert cpe.cpe_name == "cpe:2.3:a:haxx:curl:8.4.0:*:*:*:*:*:*:*"
