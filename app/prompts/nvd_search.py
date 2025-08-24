import asyncio
import json
import re

from http_mcp.mcp_types.content import TextContent
from http_mcp.mcp_types.prompts import PromptMessage
from http_mcp.types import Arguments
from pydantic import BaseModel, Field, field_validator

from app.tools.models import SearchCPEInput, SearchCVEInput
from app.tools.nvd_dal import search_cpe, search_cve

MAX_VERSION_LENGTH = 15
MAX_NAME_LENGTH = 100
MIN_LENGTH = 2

class NVDSearchInput(BaseModel):
    dependency_name: str = Field(description="The name of the dependency to search for")
    dependency_version: str = Field(description="The version of the dependency to search for")

    @field_validator("dependency_name", mode="after")
    @classmethod
    def validate_dependency_name(cls, name: str) -> str:
        if len(name) < MIN_LENGTH or len(name) > MAX_NAME_LENGTH:
            message = f"Dependency name must be between {MIN_LENGTH} and {MAX_NAME_LENGTH} "
            "characters long"
            raise ValueError(message)

        if not name.isalnum():
            message = "Dependency name must be alphanumeric"
            raise ValueError(message)

        return name.lower()

    @field_validator("dependency_version", mode="after")
    @classmethod
    def validate_dependency_version(cls, version: str) -> str:
        if len(version) < MIN_LENGTH or len(version) > MAX_VERSION_LENGTH:
            message = f"Dependency version must be between {MIN_LENGTH} and {MAX_VERSION_LENGTH} "
            "characters long"
            raise ValueError(message)

        if not re.match(r"^[0-9]+\.[0-9]+\.[0-9]+$", version):
            message = "Dependency version must be a valid semver"
            raise ValueError(message)

        return version


def sync_nvd_search(args: Arguments[NVDSearchInput]) -> tuple[PromptMessage, ...]: #type: ignore[type-arg]
    """Search for vulnerabilities in a dependency model controlled version."""
    message = f"Search for vulnerabilities in {args.inputs.dependency_name} "
    f"{args.inputs.dependency_version}"
    return (PromptMessage(role="user", content=TextContent(text=message)),)


async def async_nvd_search(args: Arguments[NVDSearchInput]) -> tuple[PromptMessage, ...]: #type: ignore[type-arg]
    """Search for vulnerabilities in a dependency fast version."""
    cpe_results = search_cpe(
        Arguments(
            inputs=SearchCPEInput(
                product=args.inputs.dependency_name,
                version=args.inputs.dependency_version,
            ),
            request=args.request,
        ),
    )
    cve_results = await asyncio.gather(
        *[
            search_cve(
                Arguments(
                    inputs=SearchCVEInput(cpe_name=cpe.cpe_name),
                    request=args.request,
                ),
            )
            for cpe in cpe_results.cpes
        ],
    )
    message = (
        f"The following <cves> were found for {args.inputs.dependency_name} "
        f"{args.inputs.dependency_version}: "
        "<cves>\n{cve_results}\n</cves>"
    )
    return (
        PromptMessage(
            role="user",
            content=TextContent(text=message.format(cve_results=json.dumps(cve_results, indent=2))),
        ),
    )
