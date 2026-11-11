# ChangeScope GitHub App Integration Guide

This guide details the procedure for registering, configuring, and deploying the **ChangeScope GitHub App**. The integration inspects proposed pull requests, evaluates API contract changes, traverses transitive blast radiuses, correlates runtime OpenTelemetry traces, and publishes actionable, non-blocking intelligence reports directly to GitHub.

---

## 1. Architectural Overview

```
   ┌──────────────────────────────────────────────────────────────┐
   │                          GitHub.com                          │
   │  ┌───────────────────┐               ┌────────────────────┐  │
   │  │   Pull Request    │               │     Check Runs     │  │
   │  │ (opened/synced)   │               │   & PR Comments    │  │
   │  └────────┬──────────┘               └────────▲───────────┘  │
   └───────────┼───────────────────────────────────┼──────────────┘
               │ Webhook (HMAC-SHA256)             │ REST API
               ▼                                   │ (Check Run / Comment)
   ┌───────────────────────────────────────────────┴──────────────┐
   │                     ChangeScope Platform                     │
   │                                                              │
   │  1. Webhook Signature Verification & Delivery Deduplication   │
   │  2. Repository Boundary & Tenancy Isolation Verification     │
   │  3. Diff Extraction (Patch hunks, modified symbols)          │
   │  4. Contract & Semantic Reasoning (OpenAPI, JSON Schema)     │
   │  5. Blast Radius Graph Traversal (Neo4j / In-Memory Graph)   │
   │  6. Runtime Trace Evidence Correlation (OpenTelemetry)       │
   │  7. Remediation Test Recommendations (Pending Human Review)   │
   │  8. Formatter: Publishes 8-Section Non-Blocking Report       │
   └──────────────────────────────────────────────────────────────┘
```

---

## 2. Registering the GitHub App

1. Navigate to **GitHub Settings** > **Developer Settings** > **GitHub Apps** > **New GitHub App**.
2. **App Configuration**:
   - **GitHub App name**: `ChangeScope Change Intelligence` (or your organizational identifier).
   - **Homepage URL**: `https://changescope.io` (or your internal ChangeScope web portal URL).
   - **Callback URL**: `https://<your-domain>/api/v1/auth/github/callback` (optional, for OAuth user authentication).
3. **Webhook Setup**:
   - **Webhook URL**: `https://<your-domain>/api/v1/webhooks/github`
   - **Webhook secret**: Generate a secure 32+ character random secret:
     ```bash
     openssl rand -hex 32
     ```
   - Store this secret securely; it must match `CHANGESCOPE_GITHUB_WEBHOOK_SECRET`.
4. **Permissions Configuration**:
   Configure the following granular permissions:

   | Permission Type | Resource | Access Level | Rationale |
   | :--- | :--- | :--- | :--- |
   | **Repository** | **Checks** | `Read and write` | Publish Check Runs with line-level code annotations. |
   | **Repository** | **Pull requests** | `Read and write` | Retrieve PR diffs and publish markdown summary comments. |
   | **Repository** | **Contents** | `Read-only` | Fetch commit metadata and compare base and head revisions. |
   | **Repository** | **Metadata** | `Read-only` | Mandatory for all GitHub Apps to read basic repository metadata. |

5. **Subscribe to Events**:
   Under **Subscribe to events**, select:
   - [x] **Pull request** (`opened`, `synchronize`, `reopened`)
   - [x] **Push**
   - [x] **Installation** and **Installation target**
6. Click **Create GitHub App**.

---

## 3. Generating and Storing Credentials

### 3.1 GitHub App ID & Client ID
- Copy the numeric **App ID** (e.g. `123456`) and the alphanumeric **Client ID** from the General settings page.

### 3.2 Private Key (RS256)
1. On the App settings page, scroll down to **Private keys**.
2. Click **Generate a private key**.
3. A `.pem` RSA private key file will download. Store this key securely.
4. Export the private key as an environment variable or load it from disk into ChangeScope:
   ```bash
   CHANGESCOPE_GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----"
   ```

---

## 4. Environment Configuration

Add the following variables to your `.env` or secrets manager:

```ini
# --- GitHub App & Webhook Configuration ---
CHANGESCOPE_GITHUB_APP_ID=123456
CHANGESCOPE_GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
CHANGESCOPE_GITHUB_APP_CLIENT_ID=Iv1.your_client_id
CHANGESCOPE_GITHUB_APP_CLIENT_SECRET=your_client_secret
CHANGESCOPE_GITHUB_WEBHOOK_SECRET=your_generated_webhook_hmac_secret

# Base API URL (override only for GitHub Enterprise Server)
CHANGESCOPE_GITHUB_API_BASE_URL=https://api.github.com

# Non-Blocking Default Policy (neutral, success, action_required)
CHANGESCOPE_GITHUB_CHECK_RUN_CONCLUSION_DEFAULT=neutral

# Maximum retries on HTTP 429 rate limit
CHANGESCOPE_GITHUB_RATE_LIMIT_RETRIES=3

# Frontend Dashboard URL for report deep links
CHANGESCOPE_FRONTEND_URL=https://app.changescope.io
```

---

## 5. Installing the App on Repositories

1. In the GitHub App settings, click **Install App** in the left sidebar.
2. Select your Organization or User account.
3. Choose **Only select repositories** and pick the repositories to be monitored by ChangeScope.
4. Verify that the repository is registered in ChangeScope:
   - The repository `name` (e.g. `acme/orders-service`) or `clone_url` must match an active `Repository` entity in PostgreSQL.
   - Any webhook received for an unregistered repository is rejected with `status: "UNAUTHORIZED_REPOSITORY"`, ensuring multi-tenant isolation.

---

## 6. PR Analysis Output Structure

ChangeScope publishes an 8-section report to every evaluated Pull Request:

1. **Change Summary**: Counts of touched files, contract breaking changes, semantic risk anomalies, and impacted services.
2. **Breaking Changes**: Strict table of deleted endpoints, changed parameter schemas, required field additions, or column constraints.
3. **Semantic Risks**: Subtle business mismatches (e.g., currency subunit transitions, timestamp unit discrepancies, enum semantic drift).
4. **Affected Downstream Services**: Graph-traversed consumer services with blast radius hop distances.
5. **Runtime Evidence**: OpenTelemetry verified service communication traces with traffic sampling disclaimers.
6. **Impact Paths**: Visual graph traversal hops linking the modified entity to the downstream consumer.
7. **Recommended Regression Tests**: Synthesized concrete test specifications flagged as `PENDING_HUMAN_REVIEW`.
8. **Confidence and Uncertainty**: Deterministic engine confidence score, uncertainty factors, and direct link to the full interactive dashboard.

---

## 7. Security & Reliability Invariants

- **Informational Default**: The check run `conclusion` defaults to `"neutral"` to avoid blocking critical CI/CD pipelines unless explicit organizational gating policies are enabled.
- **Zero Secrets in Logs**: All tokens (`ghs_*`, `ghp_*`, Bearer tokens) and RSA private keys are scrubbed and masked (`gh_***[REDACTED]`) before output to any log stream.
- **Anti-Replay & Deduplication**: The `X-GitHub-Delivery` GUID is tracked with an expiration window to prevent duplicate scans on webhook retries.
- **Rate Limit Resilience**: The client observes `Retry-After` and `x-ratelimit-reset` headers, implementing exponential backoff across 3 attempts before failure.
