from typing import Any, Dict, Optional
import uuid


def success_response(data: Any, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if isinstance(data, dict):
        res = dict(data)
        if meta:
            res["_meta"] = meta
        return res
    return {"data": data, "_meta": meta or {}}


def error_response(
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "details": details or {},
        "trace_id": trace_id or str(uuid.uuid4()),
    }
