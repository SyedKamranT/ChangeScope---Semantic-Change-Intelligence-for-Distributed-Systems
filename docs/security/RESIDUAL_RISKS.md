# ChangeScope: Residual Security & Reliability Risks

> [!IMPORTANT]
> **Regulatory & Certification Disclaimer:**  
> ChangeScope **does not claim** formal security certifications (including but not limited to SOC 2 Type I/II, ISO/IEC 27001, FedRAMP, PCI-DSS, or Common Criteria). The defensive mechanisms implemented across the codebase represent software engineering best practices, tenant isolation boundaries, and automated controls, but do not substitute for an independent third-party compliance audit or penetration test.

---

## 1. Executive Context

While ChangeScope implements defense-in-depth protections across authentication, authorization, tenancy, application input validation, encryption at rest, and execution reliability, every distributed software system retains inherent operational and architectural risks. This document articulates these residual risks and details recommended operational hardening for production deployments.

---

## 2. Enumeration of Residual Risks

### 2.1 Client-Side Credential & Token Compromise
* **Risk Description:** An attacker who compromises a developer workstation, CI/CD pipeline environment variable, or session cookie can impersonate an authenticated principal until token expiration.
* **Current Mitigation:** Cryptographic JWT signature verification, short-lived tokens (configurable via `JWT_EXPIRE_MINUTES`), HttpOnly/Secure/SameSite cookie flags, and audit event logging.
* **Residual Exposure:** ChangeScope does not maintain a distributed distributed real-time revocation list (blocklist) for short-lived access tokens. A valid, unexpired token will be honored until its `exp` timestamp elapses unless centralized Redis token invalidation is deployed.

### 2.2 Upstream OIDC Provider Disruption or Key Compromise
* **Risk Description:** If an enterprise's external OpenID Connect identity provider (e.g., Okta, Entra ID, Auth0) suffers an outage, key compromise, or misconfiguration, authentication into ChangeScope may be disrupted or spoofed.
* **Current Mitigation:** Mandatory `iss` and `aud` verification, asymmetric RS256 key retrieval with dynamic key rotation handling, and timeout-bounded discovery (`5.0s`).
* **Residual Exposure:** Total outage of the external OIDC discovery endpoint prevents user authentication. Private key compromise at the identity provider allows fraudulent JWT generation that ChangeScope cannot independently detect.

### 2.3 SSRF & DNS Rebinding in Complex Multi-Homed Networks
* **Risk Description:** Advanced DNS rebinding attacks where an attacker controls an authoritative nameserver that alternates between an external public IP (during validation) and an internal private IP (during subsequent HTTP socket connection).
* **Current Mitigation:** `SSRFProtector` performs synchronous DNS resolution over all returned IP records, verifying that zero resolved addresses fall within private, loopback, link-local (`169.254.169.254`), or multicast subnets.
* **Residual Exposure:** If downstream HTTP clients perform a second, un-pinned DNS resolution rather than connecting directly to the pre-validated socket address, a time-of-check to time-of-use (TOCTOU) DNS rebinding window theoretically exists.

### 2.4 Volumetric Distributed Denial of Service (DDoS)
* **Risk Description:** Coordinated volumetric layer 3/4 or layer 7 flood attacks exceeding host bandwidth, ingress socket limits, or database connection pool limits.
* **Current Mitigation:** Sliding-window rate limiting per tenant/IP (Redis with in-memory fallback), maximum request payload size limits, request timeout deadlines (`30s`), and connection pooling with overflow limits.
* **Residual Exposure:** Application-level rate limiting cannot mitigate network-level saturation (SYN floods, UDP amplification). Volumetric DDoS defense requires upstream cloud scrubbers (e.g., Cloudflare, AWS Shield, Google Cloud Armor).

### 2.5 Obfuscated & Adversarial AST Payloads
* **Risk Description:** Extremely large, cyclically recursive, or malformed source code files crafted specifically to induce AST parser stack overflows or CPU exhaustion in Tree-sitter grammars.
* **Current Mitigation:** Max file size limits (`10MB`), max archive member counts (`10,000`), execution timeout deadlines, and parser memory isolation in non-evaluating mode (code is never dynamically executed).
* **Residual Exposure:** Specially crafted regular expressions in user schemas may induce catastrophic backtracking (ReDoS) in un-sandboxed regex evaluation engines.

### 2.6 Cryptographic Key Lifecycle & Master Secret Storage
* **Risk Description:** Compromise of the master encryption key (`JWT_SECRET` or dedicated encryption secret) compromises encrypted integration credentials stored at rest.
* **Current Mitigation:** Authenticated encryption using AES-256-GCM with cryptographically random 96-bit nonces per record; minimum 32-character key validation at startup.
* **Residual Exposure:** In the default configuration, secrets are derived from environment variables. If host environment variables or container memory dumps are exposed, credentials can be decrypted. Production environments should utilize hardware security modules (HSM) or cloud secret managers (e.g., AWS KMS, HashiCorp Vault).

---

## 3. Recommended Production Hardening Checklist

| Domain | Recommended Action | Operational Priority |
| :--- | :--- | :--- |
| **Network & Ingress** | Terminate TLS 1.3 at an enterprise Edge Gateway / Cloud WAF with managed DDoS protection. | Critical |
| **Secret Management** | Mount encryption keys via HashiCorp Vault or cloud KMS instead of static `.env` files. | Critical |
| **Container Sandboxing** | Run API and worker processes with `read_only_rootfs: true`, `cap_drop: [ALL]`, and non-root UID `10001`. | High |
| **Database Encryption** | Enable PostgreSQL Transparent Data Encryption (TDE) and encrypted EBS/Persistent Volumes. | High |
| **Audit SIEM Shipping** | Forward PostgreSQL `audit_logs` to an append-only, tamper-evident SIEM (e.g., Datadog, Splunk). | Medium |
| **Token Revocation** | Back session tracking with Redis cluster to enable instantaneous administrative session termination. | Medium |
