from __future__ import annotations
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

from libs.common.exceptions import UnauthorizedError, ForbiddenError


class Permissions:
    CAN_VIEW_BARBER_RECORDS = "can_view_barber_records"
    CAN_VIEW_BARBER_CLIENTS = "can_view_barber_clients"
    CAN_VIEW_BARBER_SERVICES = "can_view_barber_services"
    CAN_VIEW_BARBER_HISTORY = "can_view_barber_history"
    CAN_VIEW_SALARY = "can_view_salary"
    CAN_VIEW_CASHBOX = "can_view_cashbox"

    ALL = [
        CAN_VIEW_BARBER_RECORDS,
        CAN_VIEW_BARBER_CLIENTS,
        CAN_VIEW_BARBER_SERVICES,
        CAN_VIEW_BARBER_HISTORY,
        CAN_VIEW_SALARY,
        CAN_VIEW_CASHBOX,
    ]


@dataclass
class JWTUser:
    user_id: str
    company_id: str
    role: str
    permissions: List[str] = field(default_factory=list)
    sid: Optional[str] = None
    email: Optional[str] = None
    is_authenticated: bool = True

    def has_perm(self, perm: str) -> bool:
        if self.role == "owner":
            return True
        return perm in self.permissions


class KeyManager:
    """Manages RSA keys and JWKS for RS256 JWT tokens."""

    _private_key_pem: Optional[str] = None
    _public_key_pem: Optional[str] = None
    _jwks: Optional[Dict[str, Any]] = None
    _kid: str = "nurcrm-key-1"

    @classmethod
    def initialize_keys(cls, private_pem_path: Optional[str] = None, public_pem_path: Optional[str] = None) -> None:
        if private_pem_path and os.path.exists(private_pem_path):
            with open(private_pem_path, "r") as f:
                cls._private_key_pem = f.read()
        if public_pem_path and os.path.exists(public_pem_path):
            with open(public_pem_path, "r") as f:
                cls._public_key_pem = f.read()

        if not cls._private_key_pem or not cls._public_key_pem:
            # Generate in-memory RSA keypair
            key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend(),
            )
            cls._private_key_pem = key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ).decode("utf-8")
            cls._public_key_pem = key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode("utf-8")

        # Compute JWKS representation
        public_key = serialization.load_pem_public_key(cls._public_key_pem.encode("utf-8"))
        numbers = public_key.public_numbers()
        import base64

        def int_to_b64(val: int) -> str:
            val_bytes = val.to_bytes((val.bit_length() + 7) // 8, byteorder="big")
            return base64.urlsafe_b64encode(val_bytes).decode("utf-8").rstrip("=")

        cls._jwks = {
            "keys": [
                {
                    "kty": "RSA",
                    "use": "sig",
                    "alg": "RS256",
                    "kid": cls._kid,
                    "n": int_to_b64(numbers.n),
                    "e": int_to_b64(numbers.e),
                }
            ]
        }

    @classmethod
    def get_private_key(cls) -> str:
        if not cls._private_key_pem:
            cls.initialize_keys()
        return cls._private_key_pem

    @classmethod
    def get_public_key(cls) -> str:
        if not cls._public_key_pem:
            cls.initialize_keys()
        return cls._public_key_pem

    @classmethod
    def get_jwks(cls) -> Dict[str, Any]:
        if not cls._jwks:
            cls.initialize_keys()
        return cls._jwks


# Initialize keys at import time
KeyManager.initialize_keys()


def create_access_token(
    user_id: str,
    company_id: str,
    role: str,
    permissions: List[str],
    sid: Optional[str] = None,
    email: Optional[str] = None,
    expires_in_minutes: int = 15,
) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "company_id": str(company_id),
        "role": role,
        "permissions": permissions,
        "sid": sid or str(uuid.uuid4()),
        "email": email or "",
        "iat": now,
        "exp": now + (expires_in_minutes * 60),
    }
    return jwt.encode(
        payload,
        KeyManager.get_private_key(),
        algorithm="RS256",
        headers={"kid": KeyManager._kid},
    )


def create_refresh_token(
    user_id: str,
    company_id: str,
    sid: str,
    expires_in_days: int = 7,
) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "company_id": str(company_id),
        "sid": sid,
        "type": "refresh",
        "iat": now,
        "exp": now + (expires_in_days * 86400),
    }
    return jwt.encode(
        payload,
        KeyManager.get_private_key(),
        algorithm="RS256",
        headers={"kid": KeyManager._kid},
    )


def verify_token(token: str) -> JWTUser:
    try:
        payload = jwt.decode(
            token,
            KeyManager.get_public_key(),
            algorithms=["RS256"],
            options={"verify_exp": True},
        )
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Token has expired")
    except Exception as e:
        raise UnauthorizedError(f"Invalid token: {str(e)}")

    return JWTUser(
        user_id=payload.get("sub", ""),
        company_id=payload.get("company_id", ""),
        role=payload.get("role", "master"),
        permissions=payload.get("permissions", []),
        sid=payload.get("sid"),
        email=payload.get("email"),
    )


def create_internal_token(sender_service: str, target_service: str, expires_in_minutes: int = 5) -> str:
    now = int(time.time())
    payload = {
        "sub": sender_service,
        "aud": target_service,
        "type": "internal",
        "iat": now,
        "exp": now + (expires_in_minutes * 60),
    }
    return jwt.encode(
        payload,
        KeyManager.get_private_key(),
        algorithm="RS256",
        headers={"kid": KeyManager._kid},
    )


def verify_internal_token(token: str, expected_audience: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            KeyManager.get_public_key(),
            algorithms=["RS256"],
            audience=expected_audience,
            options={"verify_exp": True},
        )
        return payload
    except Exception as e:
        raise UnauthorizedError(f"Invalid internal token: {str(e)}")
