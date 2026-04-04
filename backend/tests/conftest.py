from __future__ import annotations

import functools

import nvdlib
import pytest
from pymocks import Mock


class FakeNvdlibCVE:
    """Mimics an nvdlib CVE object as returned after getvars() is called."""

    def __init__(self, **kwargs: object) -> None:
        self.__dict__.update(kwargs)


class FakeNvdlibCPE:
    """Mimics an nvdlib CPE object as returned by searchCPE."""

    def __init__(self, **kwargs: object) -> None:
        self.__dict__.update(kwargs)


def make_fake_cve(
    *,
    cve_id: str = "CVE-2023-44487",
    source_identifier: str = "cve@mitre.org",
    published: str = "2023-10-10T14:15:10.883",
    last_modified: str = "2024-06-27T18:34:20.870",
    vuln_status: str = "Analyzed",
    score: list[object] | None = None,
    url: str | None = None,
) -> FakeNvdlibCVE:
    if score is None:
        score = ["V31", 7.5, "HIGH"]
    if url is None:
        url = f"https://nvd.nist.gov/vuln/detail/{cve_id}"
    return FakeNvdlibCVE(
        id=cve_id,
        sourceIdentifier=source_identifier,
        published=published,
        lastModified=last_modified,
        vulnStatus=vuln_status,
        descriptions=[
            FakeNvdlibCVE(value="HTTP/2 rapid reset attack", lang="en"),
        ],
        score=score,
        weaknesses=[
            FakeNvdlibCVE(
                source="nvd@nist.gov",
                type="Primary",
                description=[FakeNvdlibCVE(lang="en", value="CWE-400")],
            ),
        ],
        references=[
            FakeNvdlibCVE(
                url="https://example.com/advisory",
                source="cve@mitre.org",
                tags=["Vendor Advisory"],
            ),
        ],
        url=url,
    )


def make_fake_cpe(
    *,
    cpe_name: str = "cpe:2.3:a:haxx:curl:8.4.0:*:*:*:*:*:*:*",
    cpe_name_id: str = "abc-123",
    deprecated: bool = False,
    last_modified: str = "2023-10-01T00:00:00.000",
    created: str = "2023-09-01T00:00:00.000",
) -> FakeNvdlibCPE:
    return FakeNvdlibCPE(
        deprecated=deprecated,
        cpeName=cpe_name,
        cpeNameId=cpe_name_id,
        lastModified=last_modified,
        created=created,
        titles=[FakeNvdlibCPE(title="curl 8.4.0", lang="en")],
        refs=[FakeNvdlibCPE(ref="https://curl.se", type="Vendor")],
    )


class SearchCVECapture:
    """Captures kwargs passed to the fake searchCVE and returns fake results."""

    def __init__(self, results: list[object] | None = None) -> None:
        self.results: list[object] = results if results is not None else [make_fake_cve()]
        self.captured_kwargs: dict[str, object] = {}

    def __call__(self, **kwargs: object) -> list[object]:
        self.captured_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        return self.results


class SearchCPECapture:
    """Captures kwargs passed to the fake searchCPE and returns fake results."""

    def __init__(self, results: list[object] | None = None) -> None:
        self.results: list[object] = results if results is not None else [make_fake_cpe()]
        self.captured_kwargs: dict[str, object] = {}

    def __call__(self, **kwargs: object) -> list[object]:
        self.captured_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        return self.results


@pytest.fixture
def fake_search_cve() -> SearchCVECapture:
    return SearchCVECapture()


@pytest.fixture
def fake_search_cpe() -> SearchCPECapture:
    return SearchCPECapture()


@pytest.fixture
def mock_search_cve(fake_search_cve: SearchCVECapture) -> Mock:
    @functools.wraps(nvdlib.searchCVE)
    def wrapper(*args: object, **kwargs: object) -> object:
        return fake_search_cve(*args, **kwargs)

    return Mock(
        module_where_used=nvdlib,
        current_value=nvdlib.searchCVE,
        new_value=wrapper,
    )


@pytest.fixture
def mock_search_cpe(fake_search_cpe: SearchCPECapture) -> Mock:
    @functools.wraps(nvdlib.searchCPE)
    def wrapper(*args: object, **kwargs: object) -> object:
        return fake_search_cpe(*args, **kwargs)

    return Mock(
        module_where_used=nvdlib,
        current_value=nvdlib.searchCPE,
        new_value=wrapper,
    )
