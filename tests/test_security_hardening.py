"""
Comprehensive security tests for MYND backend.

Tests OWASP Top 10 vulnerabilities:
- A02:2021 - Cryptographic Failures
- A03:2021 - Injection
- A05:2021 - Broken Access Control
- A06:2021 - Vulnerable and Outdated Components

Run with: pytest tests/test_security_hardening.py -v
"""

import unittest
import tempfile
import os
import zipfile
import json
from unittest.mock import Mock, patch, MagicMock

from backend.core.security_hardening import (
    ServiceURL,
    Credentials,
    CSRFProtection,
    InputSanitizer,
    URLValidationError,
    CredentialValidationError,
    SecureConfigLoader,
    FilePathValidator,
    ValidationError,
    mask_value_for_logging,
)


class TestServiceURLValidation(unittest.TestCase):
    """Test SSRF prevention (A06:2021 - Vulnerable Components)."""

    def test_valid_https_url(self):
        """Valid HTTPS URL should be accepted."""
        url = ServiceURL("https://nextcloud.example.com")
        self.assertIn("nextcloud.example.com", str(url))

    def test_auto_https_prefix(self):
        """URL without scheme should get https prefix."""
        url = ServiceURL("nextcloud.example.com")
        self.assertTrue(str(url).startswith("https://"))

    def test_block_localhost(self):
        """Localhost addresses should be blocked by default."""
        with self.assertRaises(URLValidationError):
            ServiceURL("http://localhost:8080")

    def test_block_loopback_ip(self):
        """Loopback IP should be blocked by default."""
        with self.assertRaises(URLValidationError):
            ServiceURL("http://127.0.0.1:8080")

    def test_block_private_network(self):
        """Private IPs should be blocked by default."""
        private_ips = [
            "192.168.1.1",
            "10.0.0.1",
            "172.16.0.1",
        ]
        for ip in private_ips:
            with self.assertRaises(URLValidationError):
                ServiceURL(f"http://{ip}")

    def test_allow_private_network_when_enabled(self):
        """Private IPs should be allowed when explicitly enabled."""
        url = ServiceURL(
            "http://192.168.1.1:8080",
            allow_private_network=True
        )
        self.assertIn("192.168.1.1", str(url))

    def test_block_embedded_credentials(self):
        """Embedded credentials in URL should be blocked (credential leak prevention)."""
        with self.assertRaises(URLValidationError):
            ServiceURL("https://user:password@nextcloud.example.com")

    def test_invalid_scheme(self):
        """Schemes other than http/https should be blocked."""
        with self.assertRaises(URLValidationError):
            ServiceURL("ftp://nextcloud.example.com")

    def test_empty_url(self):
        """Empty URL should raise error."""
        with self.assertRaises(URLValidationError):
            ServiceURL("")

    def test_url_length_limit(self):
        """Excessively long URL should be rejected."""
        long_url = "https://nextcloud.example.com/" + "a" * 3000
        with self.assertRaises(URLValidationError):
            ServiceURL(long_url)


class TestCredentialsValidation(unittest.TestCase):
    """Test credential validation (A02:2021 - Cryptographic Failures)."""

    def test_valid_credentials_with_password(self):
        """Valid credentials should be accepted."""
        creds = Credentials("user123", password="securePassword123!")
        self.assertEqual(creds.username, "user123")

    def test_valid_credentials_with_api_key(self):
        """Valid API key should be accepted."""
        creds = Credentials(
            "user123",
            api_key="abcdefghijklmnopqrst1234567890"
        )
        self.assertEqual(creds.username, "user123")

    def test_invalid_username_empty(self):
        """Empty username should be rejected."""
        with self.assertRaises(CredentialValidationError):
            Credentials("", password="password")

    def test_invalid_username_chars(self):
        """Invalid characters in username should be rejected."""
        with self.assertRaises(CredentialValidationError):
            Credentials("user@domain.com", password="password")

    def test_password_too_short(self):
        """Password below minimum length should be rejected."""
        with self.assertRaises(CredentialValidationError):
            Credentials("user123", password="short")

    def test_no_auth_method(self):
        """Missing both password and API key should raise error."""
        with self.assertRaises(CredentialValidationError):
            Credentials("user123")

    def test_masked_logging(self):
        """Credentials should be masked for logging."""
        creds = Credentials("user123", password="securePassword")
        masked = creds.mask_for_logging()
        self.assertNotIn("securePassword", masked)
        self.assertIn("***", masked)

    def test_safe_repr(self):
        """__repr__ should not leak credentials."""
        creds = Credentials("user123", password="securePassword")
        repr_str = repr(creds)
        self.assertNotIn("securePassword", repr_str)


class TestCSRFProtection(unittest.TestCase):
    """Test CSRF prevention (A01:2021 - Broken Access Control)."""

    def test_token_generation(self):
        """CSRF tokens should be cryptographically secure."""
        token1 = CSRFProtection.generate_token()
        token2 = CSRFProtection.generate_token()

        # Tokens should be unique
        self.assertNotEqual(token1, token2)

        # Tokens should be reasonably long
        self.assertGreater(len(token1), 20)
        self.assertGreater(len(token2), 20)

    def test_token_validation_matching(self):
        """Matching tokens should validate."""
        token = CSRFProtection.generate_token()
        self.assertTrue(CSRFProtection.validate_token(token, token))

    def test_token_validation_non_matching(self):
        """Non-matching tokens should not validate."""
        token1 = CSRFProtection.generate_token()
        token2 = CSRFProtection.generate_token()
        self.assertFalse(CSRFProtection.validate_token(token1, token2))

    def test_token_validation_empty(self):
        """Empty tokens should not validate."""
        self.assertFalse(CSRFProtection.validate_token("", "token"))
        self.assertFalse(CSRFProtection.validate_token("token", ""))

    def test_timing_attack_resistance(self):
        """Token comparison should use constant-time comparison."""
        token1 = CSRFProtection.generate_token()
        token2 = CSRFProtection.generate_token()

        # Both should return False, using constant-time comparison
        # (can't directly test timing, but validate behavior)
        self.assertFalse(CSRFProtection.validate_token(token1, token2))
        self.assertFalse(CSRFProtection.validate_token(token2, token1))


class TestInputSanitization(unittest.TestCase):
    """Test injection prevention (A03:2021 - Injection)."""

    def test_sanitize_search_query_length(self):
        """Search query should be length-limited."""
        long_query = "a" * 1000
        sanitized = InputSanitizer.sanitize_search_query(long_query, max_length=100)
        self.assertLessEqual(len(sanitized), 100)

    def test_sanitize_removes_control_chars(self):
        """Control characters should be removed."""
        query = "test\x00\x01\x02query"
        sanitized = InputSanitizer.sanitize_search_query(query)
        self.assertNotIn("\x00", sanitized)

    def test_detect_sql_injection_pattern_union(self):
        """SQL UNION injection should be detected."""
        payload = "'; UNION SELECT * FROM users; --"
        self.assertTrue(InputSanitizer.is_potential_sql_injection(payload))

    def test_detect_sql_injection_pattern_comment(self):
        """SQL comment injection should be detected."""
        payload = "password' OR 1=1 --"
        self.assertTrue(InputSanitizer.is_potential_sql_injection(payload))

    def test_detect_command_injection(self):
        """Command injection patterns should be detected."""
        payloads = [
            "; rm -rf /",
            "| cat /etc/passwd",
            "` id `",
            "$(whoami)",
        ]
        for payload in payloads:
            self.assertTrue(
                InputSanitizer.is_potential_command_injection(payload),
                f"Failed to detect: {payload}"
            )

    def test_benign_input_not_flagged(self):
        """Legitimate input should not be flagged."""
        safe_queries = [
            "find documents about security",
            "search for users named John",
            "list all files",
        ]
        for query in safe_queries:
            self.assertFalse(
                InputSanitizer.is_potential_sql_injection(query)
            )
            self.assertFalse(
                InputSanitizer.is_potential_command_injection(query)
            )


class TestSecureConfigLoader(unittest.TestCase):
    """Test secure config handling."""

    def test_mask_sensitive_values(self):
        """Sensitive config values should be masked."""
        config = {
            "api_key": "secret123",
            "password": "password456",
            "username": "john",
            "endpoint": "https://example.com",
        }
        masked = SecureConfigLoader.mask_sensitive_values(config)

        self.assertEqual(masked["api_key"], "***")
        self.assertEqual(masked["password"], "***")
        self.assertEqual(masked["username"], "john")
        self.assertEqual(masked["endpoint"], "https://example.com")

    def test_validate_required_keys(self):
        """Missing required keys should raise error."""
        config = {"key1": "value1"}
        required = ["key1", "key2", "key3"]

        with self.assertRaises(ValueError):
            SecureConfigLoader.validate_required_keys(config, required)

    def test_validate_required_keys_present(self):
        """All required keys present should pass."""
        config = {"key1": "value1", "key2": "value2", "key3": "value3"}
        required = ["key1", "key2", "key3"]

        # Should not raise
        SecureConfigLoader.validate_required_keys(config, required)


class TestFilePathValidator(unittest.TestCase):
    """Test path traversal prevention (CWE-22)."""

    def setUp(self):
        """Create temporary base directory."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_validate_safe_relative_path(self):
        """Safe relative path should be accepted."""
        safe_path = "documents/file.txt"
        result = FilePathValidator.validate_relative_path(safe_path, self.temp_dir)
        self.assertTrue(result.startswith(self.temp_dir))

    def test_reject_path_traversal_parent(self):
        """Path traversal with .. should be rejected."""
        evil_path = "../../../etc/passwd"
        with self.assertRaises(ValidationError):
            FilePathValidator.validate_relative_path(evil_path, self.temp_dir)

    def test_reject_absolute_path(self):
        """Absolute paths should be validated."""
        # Note: On some systems, absolute paths might be accepted if they're
        # in the same tree. This test ensures the function validates properly.
        abs_path = "/etc/passwd"
        with self.assertRaises(ValidationError):
            FilePathValidator.validate_relative_path(abs_path, self.temp_dir)

    def test_safe_nested_path(self):
        """Safe nested path should be accepted."""
        safe_path = "dir1/dir2/dir3/file.txt"
        result = FilePathValidator.validate_relative_path(safe_path, self.temp_dir)
        self.assertTrue(result.startswith(self.temp_dir))


class TestMaskValueForLogging(unittest.TestCase):
    """Test value masking for safe logging."""

    def test_empty_value_masked(self):
        """Empty values should be masked."""
        self.assertEqual(mask_value_for_logging(""), "***")
        self.assertEqual(mask_value_for_logging(None), "***")

    def test_short_value_fully_masked(self):
        """Short values should be fully masked."""
        masked = mask_value_for_logging("short")
        self.assertEqual(masked, "***")

    def test_long_value_partially_shown(self):
        """Long values should show first/last chars."""
        long_value = "abcdefghijklmnopqrstuvwxyz"
        masked = mask_value_for_logging(long_value, threshold=3)
        self.assertTrue(masked.startswith("abc"))
        self.assertTrue(masked.endswith("xyz"))


class TestPathTraversalInZip(unittest.TestCase):
    """Test ZIP path traversal prevention (CWE-22)."""

    def setUp(self):
        """Create test ZIP file with traversal attempts."""
        self.temp_dir = tempfile.mkdtemp()
        self.dangerous_zip = os.path.join(self.temp_dir, "dangerous.zip")

        # Create ZIP with path traversal
        with zipfile.ZipFile(self.dangerous_zip, "w") as zf:
            zf.writestr("normal_file.txt", "safe content")
            zf.writestr("../../../etc/passwd", "malicious")
            zf.writestr("/etc/shadow", "malicious")

    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_zip_member_validation_rejects_parent_ref(self):
        """ZIP member with .. should be rejected."""
        from backend.features.documents.parser_hardened import DocumentParser

        parser = DocumentParser()
        base_dir = tempfile.mkdtemp()

        try:
            with zipfile.ZipFile(self.dangerous_zip) as zf:
                for member in zf.infolist():
                    if ".." in member.filename or member.filename.startswith("/"):
                        with self.assertRaises(Exception):  # PathTraversalError
                            parser._validate_zip_member(member, base_dir)
        finally:
            import shutil
            shutil.rmtree(base_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
