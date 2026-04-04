import asyncio

import nvdlib
from fastapi import Request
from http_mcp.types import Arguments

from app.tools.models import (
    CPE,
    CVE,
    SearchCPEInput,
    SearchCPEOutput,
    SearchCVEInput,
    SearchCVEOutput,
)


def get_key(request: Request) -> str | None:
    key = request.headers.get("Authorization", "").strip().split(" ")[-1]
    if not key:
        return None
    return key


def search_cpe(arg: Arguments[SearchCPEInput]) -> SearchCPEOutput:
    """Search Common Platform Enumerations (CPE) for a given product and version."""
    results = tuple(
        CPE.model_validate(
            cpe,
            by_alias=True,
        )
        for cpe in nvdlib.searchCPE(
            cpeMatchString=f"cpe:2.3:a:{arg.inputs.vendor}:{arg.inputs.product}:{arg.inputs.version}",
        )
    )
    return SearchCPEOutput(cpes=results)


async def search_cve(arg: Arguments[SearchCVEInput]) -> SearchCVEOutput:
    """Search Common Vulnerabilities and Exposures (CVE) with flexible filters.

    Supports searching by CVE ID, CPE name, keyword, CWE ID, CVSS severity,
    Known Exploited Vulnerabilities, and publication date range.
    """
    field_mapping = {
        "cve_id": "cveId",
        "cpe_name": "cpeName",
        "keyword_search": "keywordSearch",
        "cwe_id": "cweId",
        "cvss_v3_severity": "cvssV3Severity",
        "has_kev": "hasKev",
        "no_rejected": "noRejected",
        "pub_start_date": "pubStartDate",
        "pub_end_date": "pubEndDate",
    }
    flag_fields = {"has_kev", "no_rejected"}
    kwargs = {
        param: getattr(arg.inputs, field)
        for field, param in field_mapping.items()
        if getattr(arg.inputs, field) is not None
        and (field not in flag_fields or getattr(arg.inputs, field))
    }
    raw_results = await asyncio.to_thread(nvdlib.searchCVE, **kwargs)
    results = tuple(
        CVE.model_validate(
            cve,
            by_alias=True,
            from_attributes=True,
        )
        for cve in raw_results
    )
    return SearchCVEOutput(cves=results)
