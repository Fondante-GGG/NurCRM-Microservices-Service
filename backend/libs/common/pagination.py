from typing import Any, List, Dict
from dataclasses import dataclass


@dataclass
class PaginationParams:
    limit: int = 20
    offset: int = 0

    @classmethod
    def from_request_params(cls, limit: Any, offset: Any, default_limit: int = 20, max_limit: int = 100) -> "PaginationParams":
        try:
            lim = int(limit) if limit is not None else default_limit
        except (ValueError, TypeError):
            lim = default_limit

        try:
            off = int(offset) if offset is not None else 0
        except (ValueError, TypeError):
            off = 0

        lim = max(1, min(lim, max_limit))
        off = max(0, off)
        return cls(limit=lim, offset=off)


def paginate_results(items: List[Any], total_count: int, params: PaginationParams) -> Dict[str, Any]:
    return {
        "count": total_count,
        "results": items,
        "limit": params.limit,
        "offset": params.offset,
    }
