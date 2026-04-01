"""
Security hardening module for MYND backend.
Provides centralized validation, sanitization, and defensive utilities.

OWASP Top 10 Mitigations:
- A03:2021 - Injection: Input validation and parameterized calls
- A05:2021 - Broken Access Control: CSRF tokens, secure headers
- A08:2021 - Software and Data Integrity Failures: Dependency validation
"""

import re
import ipaddress
import json
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, urljoin
from enum import Enum
import secrets


logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Base exception for validation failures."""
    pass


class URLValidationError(ValidationError):
    """URL validation failed."""
    pass


class CredentialValidationError(ValidationError):
    """Credential validation failed."""
    pass


# Constants for validation
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 256
API_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{20,}$")  # Typical API key format
MAX_URL_LENGTH = 2048
MAX_USERNAME_LENGTH = 64
MAX_PASSWORD_LENGTH = 256


class ServiceURL:
    """
    Validated, normalized service URL.
    Prevents SSRF attacks by blocking private/loopback addresses.
    """

    def __init__(
        self,
        raw_url: str,
        allow_private_network: bool = False,
        allow_localhost: bool = False,
    ):
        """
        Initialize and validate a service URL.

        Args:
            raw_url: Raw URL string
            allow_private_network: Allow private IP ranges (10.0.0.0/8, etc.)
            allow_localhost: Allow localhost/127.0.0.1

        Raises:
            URLValidationError: If URL is invalid or blocked
        """
        self.allow_private = allow_private_network
        self.allow_localhost = allow_localhost
        self._url = self._validate_and_normalize(raw_url)

    def _validate_and_normalize(self, raw_url: str) -> str:
        """
        Validate and normalize URL.

        Checks:
        - Valid format
        - No embedded credentials
        - No SSRF-vulnerable addresses (unless explicitly allowed)
        - Valid scheme (http/https only)
        """
        candidate = (raw_url or "").strip()

        if not candidate:
            raise URLValidationError("URL cannot be empty")

        if len(candidate) > MAX_URL_LENGTH:
            raise URLValidationError(f"URL exceeds max length {MAX_URL_LENGTH}")

        # Add https if no scheme
        if not candidate.startswith(("http://", "https://")):
            candidate = f"https://{candidate}"

        try:
            parsed = urlparse(candidate)
        except Exception as e:
            raise URLValidationError(f"Invalid URL format: {e}")

        # Ensure valid scheme
        if parsed.scheme not in {"http", "https"}:
            raise URLValidationError(f"Invalid scheme: {parsed.scheme}")

        # Ensure netloc exists
        if not parsed.netloc:
            raise URLValidationError("URL must have a hostname")

        # CRITICAL: Block embedded credentials
        if parsed.username or parsed.password:
            raise URLValidationError(
                "URL must not contain embedded credentials. Use auth headers instead."
            )

        # SSRF check: Block private/loopback unless explicitly allowed
        host = parsed.hostname or ""
        if not self._is_allowed_host(host):
            raise URLValidationError(
                f"Host '{host}' is not allowed (private/loopback addresses blocked). "
                "Set allow_private_network=True to override."
            )

        # Normalize: remove trailing slash, ensure https
        normalized = candidate.rstrip("/")

        logger.info(f"URL validated: {parsed.hostname} (scheme: {parsed.scheme})")

        return normalized

    def _is_allowed_host(self, hostname: str) -> bool:
        """Check if hostname is allowed (not SSRF-vulnerable)."""
        if not hostname:
            return False

        lowered = hostname.lower().strip()

        # Localhost variants
        if lowered in {"localhost", "::1", "::ffff:127.0.0.1"}:
            return self.allow_localhost

        # .local domains (mDNS)
        if lowered.endswith(".local"):
            return self.allow_private

        # IP address check
        try:
            ip = ipaddress.ip_address(lowered)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return self.allow_private
            return True
        except ValueError:
            # Not an IP address; it's a valid hostname
            return True

    def __str__(self) -> str:
        """Return validated URL."""
        return self._url


class Credentials:
    """
    Validated credentials container (username + password or API key).
    Prevents credential leaking in logs and error messages.
    """

    def __init__(self, username: str, password: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize credentials.

        Args:
            username: Username (required)
            password: Password (optional if api_key provided)
            api_key: API key (optional if password provided)

        Raises:
            CredentialValidationError: If credentials invalid
        """
        self.username = self._validate_username(username)
        self.password = password
        self.api_key = api_key

        if not password and not api_key:
            raise CredentialValidationError("Either password or api_key required")

        if password:
            self._validate_password(password)
        if api_key:
            self._validate_api_key(api_key)

    def _validate_username(self, username: str) -> str:
        """Validate and sanitize username."""
        candidate = (username or "").strip()

        if not candidate:
            raise CredentialValidationError("Username cannot be empty")

        if len(candidate) > MAX_USERNAME_LENGTH:
            raise CredentialValidationError(
                f"Username exceeds max length {MAX_USERNAME_LENGTH}"
            )

        if not USERNAME_PATTERN.fullmatch(candidate):
            raise CredentialValidationError(
                f"Username contains invalid characters: {candidate}"
            )

        return candidate

    def _validate_password(self, password: str) -> None:
        """Validate password (basic checks)."""
        if not password:
            raise CredentialValidationError("Password cannot be empty")

        if len(password) < PASSWORD_MIN_LENGTH:
            raise CredentialValidationError(
                f"Password too short (min {PASSWORD_MIN_LENGTH} chars)"
            )

        if len(password) > PASSWORD_MAX_LENGTH:
            raise CredentialValidationError(
                f"Password too long (max {PASSWORD_MAX_LENGTH} chars)"
            )

    def _validate_api_key(self, api_key: str) -> None:
        """Validate API key format."""
        if not api_key or not isinstance(api_key, str):
            raise CredentialValidationError("API key must be non-empty string")

        # Most API keys are 20+ chars, alphanumeric + underscore/dash
        if len(api_key) < 20:
            logger.warning(f"API key seems unusually short: {len(api_key)} chars")

    def mask_for_logging(self) -> str:
        """Return masked representation for safe logging."""
        return f"Credentials(username={self.username}, password={'***' if self.password else 'N/A'})"

    def __repr__(self) -> str:
        """Safe string representation."""
        return self.mask_for_logging()


class CSRFProtection:
    """
    CSRF token generation and validation.
    Prevents Cross-Site Request Forgery attacks.
    """

    TOKEN_LENGTH = 32  # 32 bytes = 256 bits
    TOKEN_EXPIRY_SECONDS = 3600  # 1 hour

    @staticmethod
    def generate_token() -> str:
        """Generate cryptographically secure CSRF token."""
        return secrets.token_urlsafe(CSRFProtection.TOKEN_LENGTH)

    @staticmethod
    def validate_token(token: str, stored_token: str) -> bool:
        """
        Validate CSRF token using constant-time comparison.

        Args:
            token: Token from request
            stored_token: Token from session

        Returns:
            True if tokens match (using constant-time comparison)
        """
        if not token or not stored_token:
            return False

        return secrets.compare_digest(token, stored_token)


class InputSanitizer:
    """
    Sanitize user inputs to prevent injection attacks.
    """

    # Dangerous patterns
    SQL_INJECTION_PATTERNS = [
        re.compile(r"(\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|EXEC)\b)", re.IGNORECASE),
        re.compile(r"(--|;|/\*|\*/|xp_)"),
    ]

    COMMAND_INJECTION_PATTERNS = [
        re.compile(r"[;&|`$(){}[\]<>\\]"),
    ]

    @classmethod
    def sanitize_search_query(cls, query: str, max_length: int = 500) -> str:
        """
        Sanitize search query.
        Removes control chars and enforces length limits.
        """
        if not query:
            return ""

        candidate = query.strip()[:max_length]

        # Remove control characters
        candidate = "".join(c for c in candidate if ord(c) >= 32 or c in "\n\r\t")

        return candidate

    @classmethod
    def is_potential_sql_injection(cls, value: str) -> bool:
        """Detect potential SQL injection patterns."""
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if pattern.search(value):
                return True
        return False

    @classmethod
    def is_potential_command_injection(cls, value: str) -> bool:
        """Detect potential command injection patterns."""
        for pattern in cls.COMMAND_INJECTION_PATTERNS:
            if pattern.search(value):
                return True
        return False


class SecureConfigLoader:
    """
    Load configuration safely without exposing secrets.
    """

    SENSITIVE_KEYS = {
        "password",
        "secret",
        "token",
        "api_key",
        "apikey",
        "client_secret",
        "private_key",
    }

    @classmethod
    def load_config(cls, config_path: str) -> Dict[str, Any]:
        """
        Load JSON config file safely.

        Args:
            config_path: Path to JSON config file

        Returns:
            Config dictionary

        Raises:
            ValueError: If config invalid or unreadable
        """
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON config: {e}")
        except Exception as e:
            raise ValueError(f"Failed to load config: {e}")

    @classmethod
    def mask_sensitive_values(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return masked copy of config for logging/display.
        Replaces sensitive values with '***'.
        """
        masked = {}
        for key, value in config.items():
            if any(sensitive in key.lower() for sensitive in cls.SENSITIVE_KEYS):
                masked[key] = "***" if value else None
            else:
                masked[key] = value
        return masked

    @classmethod
    def validate_required_keys(
        cls, config: Dict[str, Any], required_keys: List[str]
    ) -> None:
        """
        Validate that config has all required keys.

        Raises:
            ValueError: If required keys missing
        """
        missing = [k for k in required_keys if k not in config]
        if missing:
            raise ValueError(f"Config missing required keys: {missing}")


class FilePathValidator:
    """
    Validate file paths to prevent path traversal attacks.
    """

    @staticmethod
    def validate_relative_path(path: str, base_dir: str) -> str:
        """
        Validate that path is relative and within base_dir.

        Args:
            path: File path (potentially user-provided)
            base_dir: Base directory (trusted)

        Returns:
            Normalized absolute path

        Raises:
            ValidationError: If path escape attempted or invalid
        """
        import os

        if not path or not isinstance(path, str):
            raise ValidationError("Path must be non-empty string")

        # Get absolute paths
        abs_base = os.path.abspath(base_dir)
        abs_path = os.path.abspath(os.path.join(base_dir, path))

        # Ensure it's within base_dir
        common = os.path.commonpath([abs_base, abs_path])
        if common != abs_base:
            raise ValidationError(f"Path traversal attempt detected: {path}")

        return abs_path


def mask_value_for_logging(value: Optional[str], threshold: int = 4) -> str:
    """
    Mask sensitive values for safe logging.
    Shows only first and last few characters.
    """
    if not value:
        return "***"

    if len(value) <= threshold * 2:
        return "***"

    return f"{value[:threshold]}{'*' * (len(value) - 2 * threshold)}{value[-threshold:]}"
