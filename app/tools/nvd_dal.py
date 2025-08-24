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
            apiKey=get_key(arg.request),
        )
    )
    return SearchCPEOutput(cpes=results)


async def search_cve(arg: Arguments[SearchCVEInput]) -> SearchCVEOutput:
    """Search Common Vulnerabilities and Exposures (CVE) for a given CPE."""
    results = await asyncio.to_thread(
        nvdlib.searchCVE,
        cpeName=arg.inputs.cpe_name,
        apiKey=get_key(arg.request),
    )
    results = tuple(
        CVE.model_validate(
            cve,
            by_alias=True,
            from_attributes=True,
        )
        for cve in results
    )
    return SearchCVEOutput(cves=results)
