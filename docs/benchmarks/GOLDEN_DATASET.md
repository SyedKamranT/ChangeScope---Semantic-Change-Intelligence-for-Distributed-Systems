# ChangeScope Golden Evaluation Dataset Catalog
## Ground Truth Corpus of 52 Seeded Distributed System Change Scenarios

This document catalogs the 52 reproducible change scenarios used to evaluate ChangeScope against structural diff and static analysis baselines. Each scenario specifies exact ground truth expectations, affected entities, impact paths, and evidence sources.

---

## 1. Dataset Summary & Category Distribution

| Category | Count | Development | Holdout | Negative Controls | Ground Truth Breaking |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **DATABASE_MIGRATION_IMPACT** | 4 | 3 | 1 | 0 | 4 |
| **ENUM_SEMANTIC_CHANGES** | 3 | 2 | 1 | 1 | 2 |
| **EVENT_ORDERING_ISSUES** | 3 | 2 | 1 | 0 | 3 |
| **EVENT_SCHEMA_EVOLUTION** | 3 | 2 | 1 | 0 | 3 |
| **FIELD_REMOVAL** | 3 | 2 | 1 | 0 | 3 |
| **FIELD_RENAME** | 3 | 2 | 1 | 0 | 3 |
| **HIDDEN_DOWNSTREAM_CONSUMERS** | 3 | 2 | 1 | 0 | 3 |
| **IDENTIFIER_SEMANTIC_DRIFT** | 3 | 2 | 1 | 0 | 3 |
| **MONETARY_UNIT_CHANGE** | 4 | 3 | 1 | 0 | 4 |
| **PERMISSION_CHANGES** | 3 | 2 | 1 | 0 | 3 |
| **RUNTIME_ONLY_DEPENDENCIES** | 3 | 2 | 1 | 0 | 3 |
| **TIMESTAMP_INTERPRETATION_CHANGE** | 3 | 2 | 1 | 0 | 3 |
| **TRANSITIVE_SERVICE_DEPENDENCIES** | 4 | 3 | 1 | 0 | 4 |
| **TYPE_INCOMPATIBILITY** | 3 | 2 | 1 | 0 | 3 |
| **UNRELATED_CHANGES** | 7 | 4 | 3 | 7 | 0 |

---

## 2. Complete Scenario Catalog

### SCEN-01: Payment Payload user_id Renamed to account_id

- **Category:** `FIELD_RENAME`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `services/payment/openapi.yaml`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `FIELD_REMOVED`
- **Expected Affected Entities:** `['order_service']`
- **Expected Impact Paths:** `[['order_service', 'payment']]`
- **Evidence Sources:** `['AST:services/payment/openapi.yaml', 'OTel:order_service->payment']`
- **Expected Non-Findings:** `['SEMANTIC_DRIFT_MONETARY_UNIT', 'PERMISSION_ESCALATED']`
- **Description:** Payment gateway API renames user_id to account_id without deprecation alias.

### SCEN-02: Customer Address postal_code Renamed to zip_code

- **Category:** `FIELD_RENAME`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `services/customer/schemas.json`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `FIELD_REMOVED`
- **Expected Affected Entities:** `['shipping_service']`
- **Expected Impact Paths:** `[['shipping_service', 'customer']]`
- **Evidence Sources:** `['AST:services/customer/schemas.json']`
- **Expected Non-Findings:** `['None']`
- **Description:** Customer profile service renames postal_code to zip_code breaking shipping worker.

### SCEN-03: Inventory SKU identifier Renamed to item_barcode

- **Category:** `FIELD_RENAME`
- **Evaluation Split:** `HOLDOUT`
- **Changed Artifact:** `services/inventory/openapi.yaml`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `FIELD_REMOVED`
- **Expected Affected Entities:** `['warehouse_dispatch']`
- **Expected Impact Paths:** `[['warehouse_dispatch', 'inventory']]`
- **Evidence Sources:** `['AST:services/inventory/openapi.yaml']`
- **Expected Non-Findings:** `['None']`
- **Description:** Inventory service renames sku to item_barcode impacting warehouse dispatch service.

### SCEN-04: Checkout API Drops billing_address Field

- **Category:** `FIELD_REMOVAL`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `services/checkout/openapi.yaml`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `FIELD_REMOVED`
- **Expected Affected Entities:** `['fraud_detector']`
- **Expected Impact Paths:** `[['fraud_detector', 'checkout']]`
- **Evidence Sources:** `['AST:services/checkout/openapi.yaml']`
- **Expected Non-Findings:** `['None']`
- **Description:** Checkout service drops billing_address field, breaking fraud inspection service.

### SCEN-05: Catalog Service Drops tax_category Field

- **Category:** `FIELD_REMOVAL`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `services/catalog/openapi.yaml`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `FIELD_REMOVED`
- **Expected Affected Entities:** `['tax_engine']`
- **Expected Impact Paths:** `[['tax_engine', 'catalog']]`
- **Evidence Sources:** `['AST:services/catalog/openapi.yaml']`
- **Expected Non-Findings:** `['None']`
- **Description:** Catalog service removes tax_category, breaking accounting tax calculation service.

### SCEN-06: Authentication Token Drops tenant_id Claim

- **Category:** `FIELD_REMOVAL`
- **Evaluation Split:** `HOLDOUT`
- **Changed Artifact:** `services/auth/token_schema.json`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `FIELD_REMOVED`
- **Expected Affected Entities:** `['api_gateway']`
- **Expected Impact Paths:** `[['api_gateway', 'auth']]`
- **Evidence Sources:** `['AST:services/auth/token_schema.json']`
- **Expected Non-Findings:** `['None']`
- **Description:** JWT token issuer removes tenant_id claim, breaking all multi-tenant isolation filters.

### SCEN-07: User ID Changed from String to Integer

- **Category:** `TYPE_INCOMPATIBILITY`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `services/user/openapi.yaml`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `TYPE_INCOMPATIBILITY`
- **Expected Affected Entities:** `['notification_service']`
- **Expected Impact Paths:** `[['notification_service', 'user']]`
- **Evidence Sources:** `['AST:services/user/openapi.yaml']`
- **Expected Non-Findings:** `['None']`
- **Description:** User service switches user_id from UUID string to integer auto-increment.

### SCEN-08: Order discount_rate Changed from Number to Array

- **Category:** `TYPE_INCOMPATIBILITY`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `services/order/openapi.yaml`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `TYPE_INCOMPATIBILITY`
- **Expected Affected Entities:** `['billing_service']`
- **Expected Impact Paths:** `[['billing_service', 'order']]`
- **Evidence Sources:** `['AST:services/order/openapi.yaml']`
- **Expected Non-Findings:** `['None']`
- **Description:** Orders service switches discount_rate float to multi-tier array of discounts.

### SCEN-09: Subscription is_active Boolean to Status String

- **Category:** `TYPE_INCOMPATIBILITY`
- **Evaluation Split:** `HOLDOUT`
- **Changed Artifact:** `services/billing/openapi.yaml`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `TYPE_INCOMPATIBILITY`
- **Expected Affected Entities:** `['feature_flag_service']`
- **Expected Impact Paths:** `[['feature_flag_service', 'billing']]`
- **Evidence Sources:** `['AST:services/billing/openapi.yaml']`
- **Expected Non-Findings:** `['None']`
- **Description:** Billing switches is_active boolean to string status (ACTIVE, TRIAL, CANCELLED).

### SCEN-10: Payment amount Cents to Dollars

- **Category:** `MONETARY_UNIT_CHANGE`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `services/payment/openapi.yaml`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `True`
- **Finding Code:** `SEMANTIC_DRIFT_MONETARY_UNIT`
- **Expected Affected Entities:** `['checkout_service']`
- **Expected Impact Paths:** `[['checkout_service', 'payment']]`
- **Evidence Sources:** `['Ontology:OssieSoftwareOntology', 'AST:services/payment/openapi.yaml']`
- **Expected Non-Findings:** `['None']`
- **Description:** Amount integer changes semantics from cents (1000 = $10.00) to whole dollars (10 = $10.00).

### SCEN-11: Invoice balance USD to EUR Transition

- **Category:** `MONETARY_UNIT_CHANGE`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `services/invoice/schema.json`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `True`
- **Finding Code:** `SEMANTIC_DRIFT_MONETARY_UNIT`
- **Expected Affected Entities:** `['ledger_sync']`
- **Expected Impact Paths:** `[['ledger_sync', 'invoice']]`
- **Evidence Sources:** `['Ontology:OssieSoftwareOntology']`
- **Expected Non-Findings:** `['None']`
- **Description:** Invoice service switches default currency dimension from USD to EUR without currency code.

### SCEN-12: Micropayment fee BasisPoints to Percentage

- **Category:** `MONETARY_UNIT_CHANGE`
- **Evaluation Split:** `HOLDOUT`
- **Changed Artifact:** `services/pricing/fee_policy.json`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `True`
- **Finding Code:** `SEMANTIC_DRIFT_MONETARY_UNIT`
- **Expected Affected Entities:** `['broker_executor']`
- **Expected Impact Paths:** `[['broker_executor', 'pricing']]`
- **Evidence Sources:** `['Ontology:OssieSoftwareOntology']`
- **Expected Non-Findings:** `['None']`
- **Description:** Fee rate switches from basis points (50 bps = 0.5%) to fractional percent (0.005).

### SCEN-13: Cryptocurrency Satoshi to Bitcoin unit shift

- **Category:** `MONETARY_UNIT_CHANGE`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `services/wallet/openapi.yaml`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `True`
- **Finding Code:** `SEMANTIC_DRIFT_MONETARY_UNIT`
- **Expected Affected Entities:** `['settlement_gateway']`
- **Expected Impact Paths:** `[['settlement_gateway', 'wallet']]`
- **Evidence Sources:** `['Ontology:OssieSoftwareOntology']`
- **Expected Non-Findings:** `['None']`
- **Description:** Crypto wallet service shifts payout amount from Satoshis (100,000,000) to BTC float.

### SCEN-14: Event timestamp Epoch Seconds to Milliseconds

- **Category:** `TIMESTAMP_INTERPRETATION_CHANGE`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `services/telemetry/event_schema.json`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `True`
- **Finding Code:** `SEMANTIC_DRIFT_TIMESTAMP`
- **Expected Affected Entities:** `['metrics_aggregator']`
- **Expected Impact Paths:** `[['metrics_aggregator', 'telemetry']]`
- **Evidence Sources:** `['Ontology:OssieSoftwareOntology']`
- **Expected Non-Findings:** `['None']`
- **Description:** Telemetry event timestamp switches from Unix seconds to Unix milliseconds (both integers).

### SCEN-15: Appointment expires_at UTC to Local Timezone

- **Category:** `TIMESTAMP_INTERPRETATION_CHANGE`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `services/scheduler/openapi.yaml`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `True`
- **Finding Code:** `SEMANTIC_DRIFT_TIMESTAMP`
- **Expected Affected Entities:** `['booking_client']`
- **Expected Impact Paths:** `[['booking_client', 'scheduler']]`
- **Evidence Sources:** `['Ontology:OssieSoftwareOntology']`
- **Expected Non-Findings:** `['None']`
- **Description:** Scheduling service changes timestamp interpretation from UTC Zulu to server local time.

### SCEN-16: Session TTL Duration Minutes to Seconds

- **Category:** `TIMESTAMP_INTERPRETATION_CHANGE`
- **Evaluation Split:** `HOLDOUT`
- **Changed Artifact:** `services/session/schema.json`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `True`
- **Finding Code:** `SEMANTIC_DRIFT_TIMESTAMP`
- **Expected Affected Entities:** `['sso_gateway']`
- **Expected Impact Paths:** `[['sso_gateway', 'session']]`
- **Evidence Sources:** `['Ontology:OssieSoftwareOntology']`
- **Expected Non-Findings:** `['None']`
- **Description:** Auth session duration integer changed from minutes to seconds.

### SCEN-17: customer_id Shifts from EndUser to TenantOrg

- **Category:** `IDENTIFIER_SEMANTIC_DRIFT`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `services/crm/openapi.yaml`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `True`
- **Finding Code:** `SEMANTIC_DRIFT_IDENTIFIER`
- **Expected Affected Entities:** `['support_portal']`
- **Expected Impact Paths:** `[['support_portal', 'crm']]`
- **Evidence Sources:** `['Ontology:NvidiaAutoOntology']`
- **Expected Non-Findings:** `['None']`
- **Description:** customer_id field name remains identical but semantic concept shifts from Individual User to Organization Tenant.

### SCEN-18: device_id Shifts from HardwareMAC to AppInstanceGUID

- **Category:** `IDENTIFIER_SEMANTIC_DRIFT`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `services/push/openapi.yaml`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `True`
- **Finding Code:** `SEMANTIC_DRIFT_IDENTIFIER`
- **Expected Affected Entities:** `['notification_hub']`
- **Expected Impact Paths:** `[['notification_hub', 'push']]`
- **Evidence Sources:** `['Ontology:OssieSoftwareOntology']`
- **Expected Non-Findings:** `['None']`
- **Description:** Mobile push service redefines device_id from physical MAC to ephemeral App installation GUID.

### SCEN-19: session_token Shifts from StatefulSession to StatelessJWT

- **Category:** `IDENTIFIER_SEMANTIC_DRIFT`
- **Evaluation Split:** `HOLDOUT`
- **Changed Artifact:** `services/auth/session.yaml`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `True`
- **Finding Code:** `SEMANTIC_DRIFT_IDENTIFIER`
- **Expected Affected Entities:** `['web_proxy']`
- **Expected Impact Paths:** `[['web_proxy', 'auth']]`
- **Evidence Sources:** `['Ontology:OssieSoftwareOntology']`
- **Expected Non-Findings:** `['None']`
- **Description:** Auth service redefines session_token from Redis opaque UUID to cryptographically signed compact JWT.

### SCEN-20: OrderStatus PENDING Replaced by INITIALIZING

- **Category:** `ENUM_SEMANTIC_CHANGES`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `services/order/status.json`
- **Severity:** `WARNING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `True`
- **Finding Code:** `SEMANTIC_DRIFT_ENUM`
- **Expected Affected Entities:** `['payment_service']`
- **Expected Impact Paths:** `[['payment_service', 'order']]`
- **Evidence Sources:** `['AST:services/order/status.json']`
- **Expected Non-Findings:** `['None']`
- **Description:** OrderStatus enum replaces PENDING with INITIALIZING, breaking non-tolerant switch-case handlers.

### SCEN-21: ShipmentStatus Added AWAITING_CUSTOMS

- **Category:** `ENUM_SEMANTIC_CHANGES`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `services/shipping/openapi.yaml`
- **Severity:** `WARNING`
- **Is Breaking:** `False`
- **Is Semantic Drift:** `True`
- **Finding Code:** `SEMANTIC_DRIFT_ENUM`
- **Expected Affected Entities:** `['customer_notifier']`
- **Expected Impact Paths:** `[['customer_notifier', 'shipping']]`
- **Evidence Sources:** `['AST:services/shipping/openapi.yaml']`
- **Expected Non-Findings:** `['None']`
- **Description:** Logistics adds new intermediate enum value AWAITING_CUSTOMS to shipment state enum.

### SCEN-22: RoleType Enum Values Converted to Lowercase

- **Category:** `ENUM_SEMANTIC_CHANGES`
- **Evaluation Split:** `HOLDOUT`
- **Changed Artifact:** `services/iam/roles.json`
- **Severity:** `WARNING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `True`
- **Finding Code:** `SEMANTIC_DRIFT_ENUM`
- **Expected Affected Entities:** `['admin_console']`
- **Expected Impact Paths:** `[['admin_console', 'iam']]`
- **Evidence Sources:** `['AST:services/iam/roles.json']`
- **Expected Non-Findings:** `['None']`
- **Description:** IAM switches RoleType from uppercase ['ADMIN', 'USER'] to lowercase ['admin', 'user'].

### SCEN-23: Kafka OrderPlaced Event Drops items Array

- **Category:** `EVENT_SCHEMA_EVOLUTION`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `events/OrderPlaced.json`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `FIELD_REMOVED`
- **Expected Affected Entities:** `['inventory_reserver']`
- **Expected Impact Paths:** `[['inventory_reserver', 'OrderPlaced']]`
- **Evidence Sources:** `['AsyncAPI:events/OrderPlaced.json']`
- **Expected Non-Findings:** `['None']`
- **Description:** OrderPlaced message schema drops nested items array in favor of lazy query endpoint.

### SCEN-24: PaymentCompleted Event Type Changed from UUID to Int

- **Category:** `EVENT_SCHEMA_EVOLUTION`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `events/PaymentCompleted.json`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `TYPE_INCOMPATIBILITY`
- **Expected Affected Entities:** `['receipt_generator']`
- **Expected Impact Paths:** `[['receipt_generator', 'PaymentCompleted']]`
- **Evidence Sources:** `['AsyncAPI:events/PaymentCompleted.json']`
- **Expected Non-Findings:** `['None']`
- **Description:** PaymentCompleted event switches payment_id from UUID string to integer.

### SCEN-25: UserRegistered Event Envelope Structure Flattened

- **Category:** `EVENT_SCHEMA_EVOLUTION`
- **Evaluation Split:** `HOLDOUT`
- **Changed Artifact:** `events/UserRegistered.json`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `FIELD_REMOVED`
- **Expected Affected Entities:** `['welcome_email_worker']`
- **Expected Impact Paths:** `[['welcome_email_worker', 'UserRegistered']]`
- **Evidence Sources:** `['AsyncAPI:events/UserRegistered.json']`
- **Expected Non-Findings:** `['None']`
- **Description:** Event bus drops outer metadata envelope {data: {user_id: ...}} directly exposing {user_id: ...}.

### SCEN-26: Kafka Topic Partitioning Changed from OrderID to Random

- **Category:** `EVENT_ORDERING_ISSUES`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `services/order/kafka_producer.yaml`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `EVENT_ORDERING_ASSUMPTION_VIOLATED`
- **Expected Affected Entities:** `['order_state_machine']`
- **Expected Impact Paths:** `[['order_state_machine', 'kafka_producer']]`
- **Evidence Sources:** `['AsyncAPI:services/order/kafka_producer.yaml']`
- **Expected Non-Findings:** `['None']`
- **Description:** Kafka producer switches message key from order_id to random UUID, destroying per-order FIFO ordering.

### SCEN-27: Payment SQS Queue Switched from FIFO to Standard

- **Category:** `EVENT_ORDERING_ISSUES`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `infra/sqs_payment.yaml`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `EVENT_ORDERING_ASSUMPTION_VIOLATED`
- **Expected Affected Entities:** `['ledger_service']`
- **Expected Impact Paths:** `[['ledger_service', 'sqs_payment']]`
- **Evidence Sources:** `['Infra:infra/sqs_payment.yaml']`
- **Expected Non-Findings:** `['None']`
- **Description:** AWS SQS queue upgraded/downgraded from FIFO to Standard, losing strictly once & ordering guarantees.

### SCEN-28: Workflow Engine Asynchronous Step Parallelization

- **Category:** `EVENT_ORDERING_ISSUES`
- **Evaluation Split:** `HOLDOUT`
- **Changed Artifact:** `workflows/order_fulfillment.json`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `EVENT_ORDERING_ASSUMPTION_VIOLATED`
- **Expected Affected Entities:** `['inventory_service']`
- **Expected Impact Paths:** `[['inventory_service', 'order_fulfillment']]`
- **Evidence Sources:** `['Workflow:workflows/order_fulfillment.json']`
- **Expected Non-Findings:** `['None']`
- **Description:** Workflow engine executes charge_card and reserve_inventory in parallel instead of sequentially.

### SCEN-29: PostgreSQL Migration Drops orders.customer_id Column

- **Category:** `DATABASE_MIGRATION_IMPACT`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `migrations/004_drop_customer_id.sql`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `DATABASE_COLUMN_DROPPED`
- **Expected Affected Entities:** `['orders_api']`
- **Expected Impact Paths:** `[['orders_api', 'migrations']]`
- **Evidence Sources:** `['SQL:migrations/004_drop_customer_id.sql']`
- **Expected Non-Findings:** `['None']`
- **Description:** Alembic DDL migration drops column customer_id while active read queries still reference it.

### SCEN-30: Adding Non-Nullable Column Without Default Value

- **Category:** `DATABASE_MIGRATION_IMPACT`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `migrations/005_add_tax_code.sql`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `DATABASE_NON_NULLABLE_NO_DEFAULT`
- **Expected Affected Entities:** `['cart_checkout']`
- **Expected Impact Paths:** `[['cart_checkout', 'migrations']]`
- **Evidence Sources:** `['SQL:migrations/005_add_tax_code.sql']`
- **Expected Non-Findings:** `['None']`
- **Description:** Migration adds mandatory column tax_code NOT NULL without DEFAULT, failing legacy INSERT statements.

### SCEN-31: PostgreSQL Column Type VARCHAR(50) Changed to UUID

- **Category:** `DATABASE_MIGRATION_IMPACT`
- **Evaluation Split:** `HOLDOUT`
- **Changed Artifact:** `migrations/006_alter_ref.sql`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `TYPE_INCOMPATIBILITY`
- **Expected Affected Entities:** `['legacy_partner_sync']`
- **Expected Impact Paths:** `[['legacy_partner_sync', 'migrations']]`
- **Evidence Sources:** `['SQL:migrations/006_alter_ref.sql']`
- **Expected Non-Findings:** `['None']`
- **Description:** Migration changes external_reference from VARCHAR(50) to strict UUID, rejecting legacy non-UUID formats.

### SCEN-32: Dropping Foreign Key Constraint and Index

- **Category:** `DATABASE_MIGRATION_IMPACT`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `migrations/007_drop_fk.sql`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `DATABASE_COLUMN_DROPPED`
- **Expected Affected Entities:** `['analytics_query_engine']`
- **Expected Impact Paths:** `[['analytics_query_engine', 'migrations']]`
- **Evidence Sources:** `['SQL:migrations/007_drop_fk.sql']`
- **Expected Non-Findings:** `['None']`
- **Description:** Migration drops foreign key index leading to sequential table scan and connection pool starvation.

### SCEN-33: Nightly Batch Billing Worker Undocumented Endpoint Consumer

- **Category:** `HIDDEN_DOWNSTREAM_CONSUMERS`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `services/account/openapi.yaml`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `ENDPOINT_REMOVED`
- **Expected Affected Entities:** `['billing_batch_worker']`
- **Expected Impact Paths:** `[['billing_batch_worker', 'account']]`
- **Evidence Sources:** `['OTel:billing_batch_worker->account', 'AST:services/account/openapi.yaml']`
- **Expected Non-Findings:** `['None']`
- **Description:** An unindexed cron job billing_batch_worker calls an undocumented /internal/accounts route dropped in PR.

### SCEN-34: Data Engineering ETL Pipeline Consuming Direct Internal Route

- **Category:** `HIDDEN_DOWNSTREAM_CONSUMERS`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `services/events/openapi.yaml`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `ENDPOINT_REMOVED`
- **Expected Affected Entities:** `['spark_etl_pipeline']`
- **Expected Impact Paths:** `[['spark_etl_pipeline', 'events']]`
- **Evidence Sources:** `['OTel:spark_etl_pipeline->events']`
- **Expected Non-Findings:** `['None']`
- **Description:** ETL spark streaming pipeline extracts raw events via internal route deleted in refactoring.

### SCEN-35: Regulatory Compliance Audit Exporter Consumer

- **Category:** `HIDDEN_DOWNSTREAM_CONSUMERS`
- **Evaluation Split:** `HOLDOUT`
- **Changed Artifact:** `services/audit/openapi.yaml`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `ENDPOINT_REMOVED`
- **Expected Affected Entities:** `['soc2_audit_collector']`
- **Expected Impact Paths:** `[['soc2_audit_collector', 'audit']]`
- **Evidence Sources:** `['OTel:soc2_audit_collector->audit']`
- **Expected Non-Findings:** `['None']`
- **Description:** SOC2 audit collector script polls /audit/trail endpoint removed during API modernization.

### SCEN-36: 3-Hop Transitive Cascade: Auth -> User -> Order -> Frontend

- **Category:** `TRANSITIVE_SERVICE_DEPENDENCIES`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `services/auth/openapi.yaml`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `FIELD_REMOVED`
- **Expected Affected Entities:** `['user_service', 'order_service', 'web_frontend']`
- **Expected Impact Paths:** `[['user_service', 'auth'], ['order_service', 'user_service', 'auth'], ['web_frontend', 'order_service', 'user_service', 'auth']]`
- **Evidence Sources:** `['AST:services/auth/openapi.yaml', 'Graph:3-hop-traversal']`
- **Expected Non-Findings:** `['None']`
- **Description:** Breaking field removal in Auth service propagates 3 hops downstream to Frontend Web App.

### SCEN-37: 4-Hop Inventory Cascade to External Courier Dispatch

- **Category:** `TRANSITIVE_SERVICE_DEPENDENCIES`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `services/inventory/openapi.yaml`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `FIELD_REMOVED`
- **Expected Affected Entities:** `['warehouse_srv', 'fulfillment_srv', 'courier_dispatcher']`
- **Expected Impact Paths:** `[['courier_dispatcher', 'fulfillment_srv', 'warehouse_srv', 'inventory']]`
- **Evidence Sources:** `['AST:services/inventory/openapi.yaml']`
- **Expected Non-Findings:** `['None']`
- **Description:** Field removal in Inventory cascades through Warehouse, Fulfillment, and Courier Dispatcher.

### SCEN-38: Transitive Payment Core to Partner Affiliate Settlement

- **Category:** `TRANSITIVE_SERVICE_DEPENDENCIES`
- **Evaluation Split:** `HOLDOUT`
- **Changed Artifact:** `services/payment_core/openapi.yaml`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `FIELD_REMOVED`
- **Expected Affected Entities:** `['ledger_service', 'settlement_gw', 'affiliate_payout']`
- **Expected Impact Paths:** `[['affiliate_payout', 'settlement_gw', 'ledger_service', 'payment_core']]`
- **Evidence Sources:** `['AST:services/payment_core/openapi.yaml']`
- **Expected Non-Findings:** `['None']`
- **Description:** Payment core removes payout_token impacting Affiliate Service via Ledger and Settlement gateways.

### SCEN-39: Multi-Branch Fan-Out Transitive Dependency

- **Category:** `TRANSITIVE_SERVICE_DEPENDENCIES`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `services/crypto_core/openapi.yaml`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `FIELD_REMOVED`
- **Expected Affected Entities:** `['card_vault', 'pii_sanitizer']`
- **Expected Impact Paths:** `[['card_vault', 'crypto_core'], ['pii_sanitizer', 'crypto_core']]`
- **Evidence Sources:** `['AST:services/crypto_core/openapi.yaml']`
- **Expected Non-Findings:** `['None']`
- **Description:** Common Core Utility removes encrypt_payload impacting two independent service branches.

### SCEN-40: Dynamic Consul Service Discovery Dynamic RPC

- **Category:** `RUNTIME_ONLY_DEPENDENCIES`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `services/pricing_calculator/openapi.yaml`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `FIELD_REMOVED`
- **Expected Affected Entities:** `['ride_dispatch_engine']`
- **Expected Impact Paths:** `[['ride_dispatch_engine', 'pricing_calculator']]`
- **Evidence Sources:** `['OTel:ride_dispatch_engine->pricing_calculator']`
- **Expected Non-Findings:** `['None']`
- **Description:** Dynamic service invocation resolved via Consul registry at runtime with zero static imports.

### SCEN-41: Cross-Cluster RabbitMQ Topic Runtime Consumer

- **Category:** `RUNTIME_ONLY_DEPENDENCIES`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `services/geo_tracking/schema.json`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `FIELD_REMOVED`
- **Expected Affected Entities:** `['fleet_map_dashboard']`
- **Expected Impact Paths:** `[['fleet_map_dashboard', 'geo_tracking']]`
- **Evidence Sources:** `['OTel:fleet_map_dashboard->geo_tracking']`
- **Expected Non-Findings:** `['None']`
- **Description:** Cross-cluster message queue consumer with dynamic routing keys unresolvable by static AST.

### SCEN-42: Polyglot gRPC Reflection Dynamic Invocation

- **Category:** `RUNTIME_ONLY_DEPENDENCIES`
- **Evaluation Split:** `HOLDOUT`
- **Changed Artifact:** `services/ml_recommender/proto.json`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `FIELD_REMOVED`
- **Expected Affected Entities:** `['recommendation_edge_gw']`
- **Expected Impact Paths:** `[['recommendation_edge_gw', 'ml_recommender']]`
- **Evidence Sources:** `['OTel:recommendation_edge_gw->ml_recommender']`
- **Expected Non-Findings:** `['None']`
- **Description:** Go gateway invokes Python ML model dynamically via gRPC Server Reflection without compiled proto stubs.

### SCEN-43: OAuth Scope Escalation: read:users to admin:users

- **Category:** `PERMISSION_CHANGES`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `services/user_mgmt/security.yaml`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `PERMISSION_REQUIREMENT_ESCALATED`
- **Expected Affected Entities:** `['dashboard_backend']`
- **Expected Impact Paths:** `[['dashboard_backend', 'user_mgmt']]`
- **Evidence Sources:** `['AST:services/user_mgmt/security.yaml']`
- **Expected Non-Findings:** `['None']`
- **Description:** User endpoint tightens required OAuth scope from read:users to admin:users, locking out service token.

### SCEN-44: mTLS Client Certificate Authorization Policy Added

- **Category:** `PERMISSION_CHANGES`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `services/secure_payout/authz.json`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `PERMISSION_REQUIREMENT_ESCALATED`
- **Expected Affected Entities:** `['batch_payout_runner']`
- **Expected Impact Paths:** `[['batch_payout_runner', 'secure_payout']]`
- **Evidence Sources:** `['SecurityPolicy:services/secure_payout/authz.json']`
- **Expected Non-Findings:** `['None']`
- **Description:** Internal payment RPC endpoint adds strict mTLS client SAN identity requirement.

### SCEN-45: Role-Based Gating Added to Document Download Endpoint

- **Category:** `PERMISSION_CHANGES`
- **Evaluation Split:** `HOLDOUT`
- **Changed Artifact:** `services/docs/routes.json`
- **Severity:** `BLOCKING`
- **Is Breaking:** `True`
- **Is Semantic Drift:** `False`
- **Finding Code:** `PERMISSION_REQUIREMENT_ESCALATED`
- **Expected Affected Entities:** `['customer_support_app']`
- **Expected Impact Paths:** `[['customer_support_app', 'docs']]`
- **Evidence Sources:** `['AST:services/docs/routes.json']`
- **Expected Non-Findings:** `['None']`
- **Description:** Document retrieval endpoint requires COMPLIANCE_OFFICER role in JWT claim.

### SCEN-46: Documentation Update in README.md

- **Category:** `UNRELATED_CHANGES`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `README.md`
- **Severity:** `NONE`
- **Is Breaking:** `False`
- **Is Semantic Drift:** `False`
- **Finding Code:** `NO_BREAKING_CHANGES`
- **Expected Affected Entities:** `['None']`
- **Expected Impact Paths:** `['None']`
- **Evidence Sources:** `['Diff:README.md']`
- **Expected Non-Findings:** `['FIELD_REMOVED', 'TYPE_INCOMPATIBILITY', 'SEMANTIC_DRIFT_MONETARY_UNIT']`
- **Description:** Developer updates markdown formatting and setup instructions in repository README.md.

### SCEN-47: Internal Helper Function Refactoring (Private Scope)

- **Category:** `UNRELATED_CHANGES`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `packages/shared/utils.py`
- **Severity:** `NONE`
- **Is Breaking:** `False`
- **Is Semantic Drift:** `False`
- **Finding Code:** `NO_BREAKING_CHANGES`
- **Expected Affected Entities:** `['None']`
- **Expected Impact Paths:** `['None']`
- **Evidence Sources:** `['AST:packages/shared/utils.py']`
- **Expected Non-Findings:** `['None']`
- **Description:** Refactoring internal private function _compute_hash inside utility module without signature change.

### SCEN-48: Adding Optional Non-Required Field with Default Value

- **Category:** `UNRELATED_CHANGES`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `services/order/openapi.yaml`
- **Severity:** `NONE`
- **Is Breaking:** `False`
- **Is Semantic Drift:** `False`
- **Finding Code:** `NO_BREAKING_CHANGES`
- **Expected Affected Entities:** `['None']`
- **Expected Impact Paths:** `['None']`
- **Evidence Sources:** `['AST:services/order/openapi.yaml']`
- **Expected Non-Findings:** `['None']`
- **Description:** Adding optional metadata field with default null value in additive, non-breaking fashion.

### SCEN-49: Unit Test Suite Additions

- **Category:** `UNRELATED_CHANGES`
- **Evaluation Split:** `HOLDOUT`
- **Changed Artifact:** `tests/unit/test_payment.py`
- **Severity:** `NONE`
- **Is Breaking:** `False`
- **Is Semantic Drift:** `False`
- **Finding Code:** `NO_BREAKING_CHANGES`
- **Expected Affected Entities:** `['None']`
- **Expected Impact Paths:** `['None']`
- **Evidence Sources:** `['Diff:tests/unit/test_payment.py']`
- **Expected Non-Findings:** `['None']`
- **Description:** Adding new unit tests in tests/unit/test_payment.py without touching service implementation.

### SCEN-50: CI/CD GitHub Actions Workflow Formatting

- **Category:** `UNRELATED_CHANGES`
- **Evaluation Split:** `DEVELOPMENT`
- **Changed Artifact:** `.github/workflows/ci.yml`
- **Severity:** `NONE`
- **Is Breaking:** `False`
- **Is Semantic Drift:** `False`
- **Finding Code:** `NO_BREAKING_CHANGES`
- **Expected Affected Entities:** `['None']`
- **Expected Impact Paths:** `['None']`
- **Evidence Sources:** `['Diff:.github/workflows/ci.yml']`
- **Expected Non-Findings:** `['None']`
- **Description:** Updating CI timeout parameter and node version in .github/workflows/ci.yml.

### SCEN-51: Docker Compose Port Forwarding Update (Dev Environment Only)

- **Category:** `UNRELATED_CHANGES`
- **Evaluation Split:** `HOLDOUT`
- **Changed Artifact:** `docker-compose.dev.yml`
- **Severity:** `NONE`
- **Is Breaking:** `False`
- **Is Semantic Drift:** `False`
- **Finding Code:** `NO_BREAKING_CHANGES`
- **Expected Affected Entities:** `['None']`
- **Expected Impact Paths:** `['None']`
- **Evidence Sources:** `['Diff:docker-compose.dev.yml']`
- **Expected Non-Findings:** `['None']`
- **Description:** Updating local docker-compose exposed debug port from 5432 to 5433.

### SCEN-52: Log Formatting and Debug Log Additions

- **Category:** `UNRELATED_CHANGES`
- **Evaluation Split:** `HOLDOUT`
- **Changed Artifact:** `services/order/handler.py`
- **Severity:** `NONE`
- **Is Breaking:** `False`
- **Is Semantic Drift:** `False`
- **Finding Code:** `NO_BREAKING_CHANGES`
- **Expected Affected Entities:** `['None']`
- **Expected Impact Paths:** `['None']`
- **Evidence Sources:** `['Diff:services/order/handler.py']`
- **Expected Non-Findings:** `['None']`
- **Description:** Adding structured log statements logger.debug('order_payload_received') inside handler.
