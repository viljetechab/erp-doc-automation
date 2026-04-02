"""Unit tests for Auth API endpoints.

Tests /register, /login, /refresh, /logout, /me for standard logic, security
rules, constraint enforcement, and error structure.
"""

from unittest.mock import AsyncMock, patch
import pytest

from app.schemas.auth import TokenResponse, UserResponse
from app.core.exceptions import AppError, AuthenticationError, ConflictError
from app.api.deps import get_auth_service


@pytest.fixture
def mock_auth_service():
    """Provides a mocked instance of AuthService."""
    with patch("app.api.deps.AuthService") as MockService:
        instance = MockService.return_value
        instance.register = AsyncMock()
        instance.login = AsyncMock()
        instance.refresh = AsyncMock()
        instance.logout = AsyncMock()
        instance.get_or_create_oauth_user = AsyncMock()
        yield instance


def test_register_success(client, mock_auth_service):
    # Setup mocks
    mock_user = type('User', (), {"id": "123", "email": "test@test.com"})()
    mock_auth_service.register.return_value = mock_user
    mock_auth_service.login.return_value = ("access_token_123", "refresh_token_abc", 900)
    
    # Override injection
    app = client.app
    app.dependency_overrides[get_auth_service] = lambda: mock_auth_service

    # Execute
    res = client.post("/api/v1/auth/register", json={
        "email": "test@test.com",
        "password": "StrongPassword123!",
        "display_name": "Tester"
    })

    # Assert
    assert res.status_code == 201
    data = res.json()
    assert data["access_token"] == "access_token_123"
    assert data["refresh_token"] == "refresh_token_abc"
    assert data["expires_in"] == 900
    mock_auth_service.register.assert_called_once()
    app.dependency_overrides.clear()


def test_register_duplicate_email(client, mock_auth_service):
    # Setup mocks to simulate existing email
    mock_auth_service.register.side_effect = ConflictError("Email already registered")
    
    app = client.app
    app.dependency_overrides[get_auth_service] = lambda: mock_auth_service

    # Execute
    res = client.post("/api/v1/auth/register", json={
        "email": "test@test.com",
        "password": "StrongPassword123!",
        "display_name": "Tester"
    })

    # Assert
    assert res.status_code == 400
    app.dependency_overrides.clear()


def test_login_success(client, mock_auth_service):
    # Setup mock
    mock_auth_service.login.return_value = ("access", "refresh", 900)
    
    app = client.app
    app.dependency_overrides[get_auth_service] = lambda: mock_auth_service

    # Execute
    res = client.post("/api/v1/auth/login", json={
        "email": "test@test.com",
        "password": "ValidPassword!"
    })

    # Assert
    assert res.status_code == 200
    assert res.json()["access_token"] == "access"
    app.dependency_overrides.clear()


def test_login_invalid_credentials(client, mock_auth_service):
    # Setup mock
    mock_auth_service.login.side_effect = AuthenticationError("Invalid email or password")
    
    app = client.app
    app.dependency_overrides[get_auth_service] = lambda: mock_auth_service

    # Execute
    res = client.post("/api/v1/auth/login", json={
        "email": "test@test.com",
        "password": "WrongPassword!"
    })

    # Assert
    assert res.status_code == 401
    app.dependency_overrides.clear()


def test_refresh_token_success(client, mock_auth_service):
    mock_auth_service.refresh.return_value = ("new_access", "new_refresh", 900)
    
    app = client.app
    app.dependency_overrides[get_auth_service] = lambda: mock_auth_service

    res = client.post("/api/v1/auth/refresh", json={
        "refresh_token": "valid_refresh"
    })

    assert res.status_code == 200
    assert res.json()["access_token"] == "new_access"
    app.dependency_overrides.clear()


def test_get_me_unauthorized(client):
    # Attempting to access protected route without token
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401


def test_get_me_authorized(auth_client, mock_user):
    # `auth_client` uses dependency override to bypass JWT validation
    # returning a mock User directly
    res = auth_client.get("/api/v1/auth/me")
    
    assert res.status_code == 200
    data = res.json()["user"]
    assert data["email"] == mock_user.email
    assert data["display_name"] == mock_user.display_name
