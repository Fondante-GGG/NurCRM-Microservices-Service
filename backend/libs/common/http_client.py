from __future__ import annotations
import time
import requests
from typing import Any, Dict, Optional
import urllib.parse

from libs.common.auth import create_internal_token
from libs.common.exceptions import CRMException, NotFoundError, ConflictError, UnauthorizedError, ForbiddenError


class InternalServiceClient:
    """HTTP client wrapper with internal JWT auth, retry backoff, timeout, and error translation."""

    def __init__(
        self,
        base_url: str,
        sender_service: str,
        target_service: str,
        timeout: float = 2.0,
        max_retries: int = 2,
    ):
        self.base_url = base_url.rstrip("/")
        self.sender_service = sender_service
        self.target_service = target_service
        self.timeout = timeout
        self.max_retries = max_retries

    def _get_headers(self, custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        token = create_internal_token(
            sender_service=self.sender_service,
            target_service=self.target_service,
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if custom_headers:
            headers.update(custom_headers)
        return headers

    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        req_headers = self._get_headers(headers)
        if idempotency_key:
            req_headers["Idempotency-Key"] = idempotency_key

        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = requests.request(
                    method=method.upper(),
                    url=url,
                    params=params,
                    json=json_data,
                    headers=req_headers,
                    timeout=self.timeout,
                )

                if resp.status_code >= 200 and resp.status_code < 300:
                    if resp.status_code == 204 or not resp.content:
                        return {}
                    return resp.json()

                # Handle error status codes
                error_body = {}
                try:
                    error_body = resp.json()
                except Exception:
                    pass

                msg = error_body.get("message", resp.text or f"HTTP {resp.status_code}")
                code = error_body.get("code", "unknown_error")
                details = error_body.get("details", {})

                if resp.status_code == 404:
                    raise NotFoundError(message=msg, code=code, details=details)
                elif resp.status_code == 409:
                    raise ConflictError(message=msg, code=code, details=details)
                elif resp.status_code == 401:
                    raise UnauthorizedError(message=msg, code=code)
                elif resp.status_code == 403:
                    raise ForbiddenError(message=msg, code=code)
                else:
                    raise CRMException(message=msg, code=code, details=details, status_code=resp.status_code)

            except (requests.ConnectionError, requests.Timeout) as e:
                last_exc = e
                if attempt < self.max_retries:
                    time.sleep(0.1 * (2 ** attempt))  # exponential backoff
                    continue
                raise CRMException(
                    message=f"Service {self.target_service} unavailable after {self.max_retries} retries: {str(e)}",
                    code="service_unavailable",
                    status_code=503,
                )

        if last_exc:
            raise CRMException(message=str(last_exc), code="service_unavailable", status_code=503)
        return {}

    def get(self, path: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        return self.request("GET", path, params=params, headers=headers)

    def post(self, path: str, json_data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        return self.request("POST", path, json_data=json_data, headers=headers, idempotency_key=idempotency_key)

    def patch(self, path: str, json_data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        return self.request("PATCH", path, json_data=json_data, headers=headers)

    def delete(self, path: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        return self.request("DELETE", path, headers=headers)
