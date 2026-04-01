import ipaddress
import re
from typing import Optional
from urllib.parse import urlparse


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def sanitize_username(username: Optional[str]) -> Optional[str]:
    """Return a safe username for file paths and lookups, else None."""
    value = (username or "").strip()
    if not value:
        return None
    if not USERNAME_PATTERN.fullmatch(value):
        return None
    return value


def mask_secret(value: Optional[str], mask: str = "***") -> str:
    """Mask secret values for API responses."""
    return mask if (value or "").strip() else ""


def is_private_or_loopback_host(hostname: str) -> bool:
    if not hostname:
        return True

    lowered = hostname.lower().strip()
    if lowered in {"localhost", "::1"}:
        return True
    if lowered.endswith(".local"):
        return True

    try:
        ip = ipaddress.ip_address(lowered)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        # Hostname is not an IP literal; keep localhost-style names blocked.
        return lowered.endswith("localhost")


def validate_service_url(raw_url: str, allow_private_network: bool = False) -> Optional[str]:
    """Validate and normalize external service URL."""
    candidate = (raw_url or "").strip()
    if not candidate:
        return None

    if not candidate.startswith(("http://", "https://")):
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        return None
    if not parsed.netloc:
        return None
    if parsed.username or parsed.password:
        # Embedded credentials are dangerous and easy to leak in logs.
        return None

    host = parsed.hostname or ""
    if is_private_or_loopback_host(host) and not allow_private_network:
        return None

    return candidate.rstrip("/")


def clamp_int(value, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))
