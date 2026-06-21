from math import ceil
from typing import Any, Dict, Generic, List, Optional, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field


T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=200)

    @property
    def skip(self) -> int:
        return (self.page - 1) * self.page_size


class PageMeta(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int
    has_next: bool
    has_prev: bool


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    pages: int
    has_next: bool = False
    has_prev: bool = False
    sort: Optional[Dict[str, Any]] = None
    filters: Optional[Dict[str, Any]] = None


def pagination_params(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
) -> PaginationParams:
    return PaginationParams(page=page, page_size=page_size)


def build_page(
    *,
    items: List[T],
    total: int,
    page: int,
    page_size: int,
    sort: Optional[Dict[str, Any]] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> PaginatedResponse[T]:
    pages = ceil(total / page_size) if total else 0
    return PaginatedResponse[T](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        has_next=page < pages,
        has_prev=page > 1 and pages > 0,
        sort=sort,
        filters=filters,
    )
