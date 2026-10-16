import pytest
import uuid
from decimal import Decimal
from datetime import datetime, timezone

from libs.common.auth import (
    create_access_token,
    create_refresh_token,
    verify_token,
    verify_refresh_token,
    create_internal_token,
    verify_internal_token,
)
from libs.common.exceptions import UnauthorizedError, ForbiddenError
from backend.services.auth.domain.models import Employee, Role, Company


def test_jwt_type_enforcement_access_vs_refresh():
    user_id = uuid.uuid4()
    company_id = uuid.uuid4()
    
    # 1. Access token
    access = create_access_token(
        user_id=str(user_id),
        company_id=str(company_id),
        role="owner",
        permissions=["all"],
        expires_in_minutes=15,
    )
    user = verify_token(access)
    assert user.user_id == str(user_id)
    assert user.company_id == str(company_id)
    
    # Access token must be rejected when verified as a refresh token
    with pytest.raises(UnauthorizedError) as exc_info:
        verify_refresh_token(access)
    assert "Invalid token type" in str(exc_info.value)

    # 2. Refresh token
    refresh = create_refresh_token(
        user_id=str(user_id),
        company_id=str(company_id),
        sid=str(uuid.uuid4()),
        expires_in_days=7,
    )
    refresh_user = verify_refresh_token(refresh)
    assert refresh_user.user_id == str(user_id)

    # Refresh token must be rejected when verified as an access token
    with pytest.raises(UnauthorizedError) as exc_info:
        verify_token(refresh)
    assert "Invalid token type" in str(exc_info.value)


def test_internal_service_token_audience_validation():
    token = create_internal_token(
        sender_service="schedule-service",
        target_service="catalog-service",
        expires_in_minutes=5,
    )

    # Valid audience
    claims = verify_internal_token(token, expected_audience="catalog-service")
    assert claims["sub"] == "schedule-service"
    assert claims["aud"] == "catalog-service"
    assert claims["type"] == "internal"

    # Audience mismatch must be rejected
    with pytest.raises(UnauthorizedError) as exc_info:
        verify_internal_token(token, expected_audience="auth-service")
    assert "Invalid audience" in str(exc_info.value)

    # Tampered token must be rejected
    tampered = token[:-5] + "XXXXX"
    with pytest.raises(UnauthorizedError):
        verify_internal_token(tampered, expected_audience="catalog-service")


def test_password_hashing_unique_salts_and_backward_compatibility():
    password = "MySecurePassword123!"
    
    # Two hashes of identical password produce distinct outputs due to random salt
    h1 = Employee.hash_password(password)
    h2 = Employee.hash_password(password)
    assert h1 != h2
    assert h1.startswith("pbkdf2_sha256$100000$")
    assert h2.startswith("pbkdf2_sha256$100000$")

    emp = Employee(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        first_name="Тест",
        last_name="Сотрудник",
        email="test@nurcrm.kg",
        phone_number="+996555123456",
        role=Role.MASTER,
        password_hash=h1,
    )
    assert emp.check_password(password) is True
    assert emp.check_password("WrongPassword") is False

    # Verify backward compatibility for seed legacy hash (static salt)
    import hashlib
    salt = "nurcrm_static_salt_2026"
    legacy_hash_val = hashlib.pbkdf2_hmac("sha256", "Password123!".encode("utf-8"), salt.encode("utf-8"), 100000).hex()
    legacy_stored = f"pbkdf2_sha256$100000${salt}${legacy_hash_val}"
    
    legacy_emp = Employee(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        first_name="Умар",
        last_name="Премиум",
        email="owner@premium.kg",
        phone_number="+996555112233",
        role=Role.OWNER,
        password_hash=legacy_stored,
    )
    assert legacy_emp.check_password("Password123!") is True
    assert legacy_emp.check_password("Wrong") is False
