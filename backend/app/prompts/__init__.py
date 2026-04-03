from http_mcp.types import Prompt

from app.prompts.nvd_search import NVDSearchInput, async_nvd_search, sync_nvd_search

PROMPTS = (
    Prompt(
        func=async_nvd_search,
        arguments_type=NVDSearchInput,
    ),
    Prompt(
        func=sync_nvd_search,
        arguments_type=NVDSearchInput,
    ),
)

__all__ = ["PROMPTS"]
