import re

from pydantic import BaseModel, Field, field_validator, model_validator

MIN_LENGTH = 2
MAX_VERSION_LENGTH = 15
MAX_NAME_LENGTH = 100


class BaseValidator(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def class_to_dict(cls, data: object) -> object:
        return data.__dict__


class CPETitles(BaseValidator):
    title: str = Field(description="Title of the CPE")
    lang: str = Field(description="Language of the title")


class CPERef(BaseValidator):
    ref: str = Field(description="Reference of the CPE")
    type: str = Field(description="Type of the reference")


class CPE(BaseValidator):
    deprecated: bool = Field(description="Indicates if the CPE is deprecated")
    cpe_name: str = Field(alias="cpeName")
    cpe_name_id: str = Field(alias="cpeNameId")
    last_modified: str = Field(alias="lastModified")
    created: str = Field(
        description="ISO 8601 date/time format including time zone. - CPE creation date",
    )
    titles: list[CPETitles] = Field(description="Titles of the CPE")
    refs: list[CPERef] = Field(description="References of the CPE")


class CVEDescription(BaseValidator):
    value: str = Field(description="Description of the CVE")
    lang: str = Field(description="Language of the description")


class WeaknessDescription(BaseValidator):
    lang: str = Field(description="Language of the description")
    value: str = Field(description="Common Weakness Enumeration Specification (CWE)")


class Weakness(BaseValidator):
    source: str = Field(description="Source of the weakness")
    type: str = Field(description="Type of the weakness")
    description: list[WeaknessDescription] = Field(description="Description of the weakness")


class CVEReference(BaseValidator):
    url: str = Field(description="URL of the reference")
    source: str = Field(description="Email of the reference")
    tags: list[str] | None = Field(description="Tags of the reference", default=None)


class CVE(BaseValidator):
    id: str = Field(description="CVE ID")
    published: str = Field(
        description="ISO 8601 date/time format including time zone. - CVE publication date",
    )
    descriptions: list[CVEDescription] = Field(description="Descriptions of the CVE")
    weaknesses: list[Weakness] = Field(description="Weaknesses of the CVE")
    references: list[CVEReference] = Field(description="References of the CVE")


class SearchCVEInput(BaseModel):
    cpe_name: str = Field(description="CPE name of the CVE")


class SearchCVEOutput(BaseModel):
    cves: tuple[CVE, ...] = Field(description="CVE of the CVE")


class SearchCPEInput(BaseModel):
    product: str = Field(description="Product of the CPE")
    version: str = Field(description="Version of the CPE")
    vendor: str = Field(description="Vendor of the CPE", default="*")

    @field_validator("product", mode="after")
    @classmethod
    def validate_product(cls, product: str) -> str:
        if len(product) < MIN_LENGTH or len(product) > MAX_NAME_LENGTH:
            message = f"Product must be between {MIN_LENGTH} and {MAX_NAME_LENGTH} characters long"
            raise ValueError(message)
        return product.lower()

    @field_validator("version", mode="after")
    @classmethod
    def validate_version(cls, version: str) -> str:
        if len(version) < MIN_LENGTH or len(version) > MAX_VERSION_LENGTH:
            message = f"Version must be between {MIN_LENGTH} and {MAX_VERSION_LENGTH} "
            "characters long"
            raise ValueError(message)
        if not re.match(r"^[0-9]+\.[0-9]+\.[0-9]+$", version):
            message = "Version must be a valid semver"
            raise ValueError(message)
        return version

    @field_validator("vendor", mode="after")
    @classmethod
    def validate_vendor(cls, vendor: str) -> str:
        if len(vendor) < MIN_LENGTH or len(vendor) > MAX_NAME_LENGTH:
            message = f"Vendor must be between {MIN_LENGTH} and {MAX_NAME_LENGTH} characters long"
            raise ValueError(message)
        return vendor.lower()


class SearchCPEOutput(BaseModel):
    cpes: tuple[CPE, ...] = Field(description="CPE of the CPE")
