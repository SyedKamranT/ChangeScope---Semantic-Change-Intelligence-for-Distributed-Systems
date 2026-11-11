"""Golden Dataset of 52 Seeded Change Scenarios across 15 Canonical Categories.

Explicitly partitioned into Development (36) and Holdout (16) splits to prevent overfitting.
"""

from packages.benchmarks.models import (
    BenchmarkScenario,
    DatasetSplit,
    GroundTruthFinding,
    ScenarioCategory,
)


def build_golden_dataset() -> list[BenchmarkScenario]:
    """Constructs the canonical 52-scenario evaluation dataset."""
    scenarios: list[BenchmarkScenario] = []

    # =========================================================================
    # Category 1: FIELD_RENAME (SCEN-01 .. SCEN-03)
    # =========================================================================
    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-01",
            name="Payment Payload user_id Renamed to account_id",
            category=ScenarioCategory.FIELD_RENAME,
            split=DatasetSplit.DEVELOPMENT,
            description="Payment gateway API renames user_id to account_id without deprecation alias.",
            changed_artifact="services/payment/openapi.yaml",
            before_state={
                "properties": {"user_id": {"type": "string"}, "amount": {"type": "integer"}},
                "required": ["user_id", "amount"],
            },
            after_state={
                "properties": {"account_id": {"type": "string"}, "amount": {"type": "integer"}},
                "required": ["account_id", "amount"],
            },
            static_graph={
                "edges": [
                    {"source": "order_service", "target": "payment", "type": "STATIC_CALL"},
                ]
            },
            runtime_traces=[{"client_service": "order_service", "target_service": "payment", "call_count_7d": 15000}],
            ground_truth=GroundTruthFinding(
                finding_code="FIELD_REMOVED",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["order_service"],
                expected_impact_paths=[["order_service", "payment"]],
                evidence_sources=["AST:services/payment/openapi.yaml", "OTel:order_service->payment"],
                description="user_id was dropped; client order_service expects user_id.",
            ),
            expected_non_findings=["SEMANTIC_DRIFT_MONETARY_UNIT", "PERMISSION_ESCALATED"],
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-02",
            name="Customer Address postal_code Renamed to zip_code",
            category=ScenarioCategory.FIELD_RENAME,
            split=DatasetSplit.DEVELOPMENT,
            description="Customer profile service renames postal_code to zip_code breaking shipping worker.",
            changed_artifact="services/customer/schemas.json",
            before_state={"properties": {"postal_code": {"type": "string"}}},
            after_state={"properties": {"zip_code": {"type": "string"}}},
            static_graph={"edges": [{"source": "shipping_service", "target": "customer", "type": "STATIC_CALL"}]},
            ground_truth=GroundTruthFinding(
                finding_code="FIELD_REMOVED",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["shipping_service"],
                expected_impact_paths=[["shipping_service", "customer"]],
                evidence_sources=["AST:services/customer/schemas.json"],
                description="postal_code missing from after schema.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-03",
            name="Inventory SKU identifier Renamed to item_barcode",
            category=ScenarioCategory.FIELD_RENAME,
            split=DatasetSplit.HOLDOUT,
            description="Inventory service renames sku to item_barcode impacting warehouse dispatch service.",
            changed_artifact="services/inventory/openapi.yaml",
            before_state={"properties": {"sku": {"type": "string"}, "quantity": {"type": "integer"}}},
            after_state={"properties": {"item_barcode": {"type": "string"}, "quantity": {"type": "integer"}}},
            static_graph={"edges": [{"source": "warehouse_dispatch", "target": "inventory", "type": "STATIC_CALL"}]},
            runtime_traces=[
                {"client_service": "warehouse_dispatch", "target_service": "inventory", "call_count_7d": 4200}
            ],
            ground_truth=GroundTruthFinding(
                finding_code="FIELD_REMOVED",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["warehouse_dispatch"],
                expected_impact_paths=[["warehouse_dispatch", "inventory"]],
                evidence_sources=["AST:services/inventory/openapi.yaml"],
                description="Field sku dropped in warehouse dispatch interface.",
            ),
        )
    )

    # =========================================================================
    # Category 2: FIELD_REMOVAL (SCEN-04 .. SCEN-06)
    # =========================================================================
    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-04",
            name="Checkout API Drops billing_address Field",
            category=ScenarioCategory.FIELD_REMOVAL,
            split=DatasetSplit.DEVELOPMENT,
            description="Checkout service drops billing_address field, breaking fraud inspection service.",
            changed_artifact="services/checkout/openapi.yaml",
            before_state={"properties": {"billing_address": {"type": "object"}, "order_id": {"type": "string"}}},
            after_state={"properties": {"order_id": {"type": "string"}}},
            static_graph={"edges": [{"source": "fraud_detector", "target": "checkout", "type": "STATIC_CALL"}]},
            runtime_traces=[{"client_service": "fraud_detector", "target_service": "checkout", "call_count_7d": 8900}],
            ground_truth=GroundTruthFinding(
                finding_code="FIELD_REMOVED",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["fraud_detector"],
                expected_impact_paths=[["fraud_detector", "checkout"]],
                evidence_sources=["AST:services/checkout/openapi.yaml"],
                description="billing_address removed from response payload.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-05",
            name="Catalog Service Drops tax_category Field",
            category=ScenarioCategory.FIELD_REMOVAL,
            split=DatasetSplit.DEVELOPMENT,
            description="Catalog service removes tax_category, breaking accounting tax calculation service.",
            changed_artifact="services/catalog/openapi.yaml",
            before_state={"properties": {"tax_category": {"type": "string"}, "price": {"type": "number"}}},
            after_state={"properties": {"price": {"type": "number"}}},
            static_graph={"edges": [{"source": "tax_engine", "target": "catalog", "type": "STATIC_CALL"}]},
            ground_truth=GroundTruthFinding(
                finding_code="FIELD_REMOVED",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["tax_engine"],
                expected_impact_paths=[["tax_engine", "catalog"]],
                evidence_sources=["AST:services/catalog/openapi.yaml"],
                description="tax_category dropped causing accounting calculation crash.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-06",
            name="Authentication Token Drops tenant_id Claim",
            category=ScenarioCategory.FIELD_REMOVAL,
            split=DatasetSplit.HOLDOUT,
            description="JWT token issuer removes tenant_id claim, breaking all multi-tenant isolation filters.",
            changed_artifact="services/auth/token_schema.json",
            before_state={"properties": {"sub": {"type": "string"}, "tenant_id": {"type": "string"}}},
            after_state={"properties": {"sub": {"type": "string"}}},
            static_graph={"edges": [{"source": "api_gateway", "target": "auth", "type": "STATIC_CALL"}]},
            runtime_traces=[{"client_service": "api_gateway", "target_service": "auth", "call_count_7d": 50000}],
            ground_truth=GroundTruthFinding(
                finding_code="FIELD_REMOVED",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["api_gateway"],
                expected_impact_paths=[["api_gateway", "auth"]],
                evidence_sources=["AST:services/auth/token_schema.json"],
                description="Critical tenant_id dropped from claims.",
            ),
        )
    )

    # =========================================================================
    # Category 3: TYPE_INCOMPATIBILITY (SCEN-07 .. SCEN-09)
    # =========================================================================
    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-07",
            name="User ID Changed from String to Integer",
            category=ScenarioCategory.TYPE_INCOMPATIBILITY,
            split=DatasetSplit.DEVELOPMENT,
            description="User service switches user_id from UUID string to integer auto-increment.",
            changed_artifact="services/user/openapi.yaml",
            before_state={"properties": {"user_id": {"type": "string"}}},
            after_state={"properties": {"user_id": {"type": "integer"}}},
            static_graph={"edges": [{"source": "notification_service", "target": "user", "type": "STATIC_CALL"}]},
            ground_truth=GroundTruthFinding(
                finding_code="TYPE_INCOMPATIBILITY",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["notification_service"],
                expected_impact_paths=[["notification_service", "user"]],
                evidence_sources=["AST:services/user/openapi.yaml"],
                description="String to integer is backwards incompatible.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-08",
            name="Order discount_rate Changed from Number to Array",
            category=ScenarioCategory.TYPE_INCOMPATIBILITY,
            split=DatasetSplit.DEVELOPMENT,
            description="Orders service switches discount_rate float to multi-tier array of discounts.",
            changed_artifact="services/order/openapi.yaml",
            before_state={"properties": {"discount_rate": {"type": "number"}}},
            after_state={"properties": {"discount_rate": {"type": "array"}}},
            static_graph={"edges": [{"source": "billing_service", "target": "order", "type": "STATIC_CALL"}]},
            ground_truth=GroundTruthFinding(
                finding_code="TYPE_INCOMPATIBILITY",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["billing_service"],
                expected_impact_paths=[["billing_service", "order"]],
                evidence_sources=["AST:services/order/openapi.yaml"],
                description="Scalar number changed to array breaks deserializers.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-09",
            name="Subscription is_active Boolean to Status String",
            category=ScenarioCategory.TYPE_INCOMPATIBILITY,
            split=DatasetSplit.HOLDOUT,
            description="Billing switches is_active boolean to string status (ACTIVE, TRIAL, CANCELLED).",
            changed_artifact="services/billing/openapi.yaml",
            before_state={"properties": {"is_active": {"type": "boolean"}}},
            after_state={"properties": {"is_active": {"type": "string"}}},
            static_graph={"edges": [{"source": "feature_flag_service", "target": "billing", "type": "STATIC_CALL"}]},
            runtime_traces=[
                {"client_service": "feature_flag_service", "target_service": "billing", "call_count_7d": 12000}
            ],
            ground_truth=GroundTruthFinding(
                finding_code="TYPE_INCOMPATIBILITY",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["feature_flag_service"],
                expected_impact_paths=[["feature_flag_service", "billing"]],
                evidence_sources=["AST:services/billing/openapi.yaml"],
                description="Boolean to string type mismatch.",
            ),
        )
    )

    # =========================================================================
    # Category 4: MONETARY_UNIT_CHANGE (SCEN-10 .. SCEN-13)
    # =========================================================================
    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-10",
            name="Payment amount Cents to Dollars",
            category=ScenarioCategory.MONETARY_UNIT_CHANGE,
            split=DatasetSplit.DEVELOPMENT,
            description="Amount integer changes semantics from cents (1000 = $10.00) to whole dollars (10 = $10.00).",
            changed_artifact="services/payment/openapi.yaml",
            before_state={
                "properties": {"amount": {"type": "integer"}},
                "ontology": {"unit": "cents", "concept": "CurrencySubunit"},
            },
            after_state={
                "properties": {"amount": {"type": "integer"}},
                "ontology": {"unit": "USD_dollars", "concept": "CurrencyMainUnit"},
            },
            static_graph={"edges": [{"source": "checkout_service", "target": "payment", "type": "STATIC_CALL"}]},
            runtime_traces=[
                {"client_service": "checkout_service", "target_service": "payment", "call_count_7d": 25000}
            ],
            ground_truth=GroundTruthFinding(
                finding_code="SEMANTIC_DRIFT_MONETARY_UNIT",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=True,
                expected_affected_entities=["checkout_service"],
                expected_impact_paths=[["checkout_service", "payment"]],
                evidence_sources=["Ontology:OssieSoftwareOntology", "AST:services/payment/openapi.yaml"],
                description="100x pricing miscalculation due to cents-to-dollars semantic transition.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-11",
            name="Invoice balance USD to EUR Transition",
            category=ScenarioCategory.MONETARY_UNIT_CHANGE,
            split=DatasetSplit.DEVELOPMENT,
            description="Invoice service switches default currency dimension from USD to EUR without currency code.",
            changed_artifact="services/invoice/schema.json",
            before_state={
                "properties": {"balance": {"type": "number"}},
                "ontology": {"unit": "USD", "concept": "CurrencyUSD"},
            },
            after_state={
                "properties": {"balance": {"type": "number"}},
                "ontology": {"unit": "EUR", "concept": "CurrencyEUR"},
            },
            static_graph={"edges": [{"source": "ledger_sync", "target": "invoice", "type": "STATIC_CALL"}]},
            ground_truth=GroundTruthFinding(
                finding_code="SEMANTIC_DRIFT_MONETARY_UNIT",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=True,
                expected_affected_entities=["ledger_sync"],
                expected_impact_paths=[["ledger_sync", "invoice"]],
                evidence_sources=["Ontology:OssieSoftwareOntology"],
                description="Cross-currency denomination shift without explicit exchange rate conversion.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-12",
            name="Micropayment fee BasisPoints to Percentage",
            category=ScenarioCategory.MONETARY_UNIT_CHANGE,
            split=DatasetSplit.HOLDOUT,
            description="Fee rate switches from basis points (50 bps = 0.5%) to fractional percent (0.005).",
            changed_artifact="services/pricing/fee_policy.json",
            before_state={
                "properties": {"fee_rate": {"type": "number"}},
                "ontology": {"unit": "basis_points", "concept": "BpsUnit"},
            },
            after_state={
                "properties": {"fee_rate": {"type": "number"}},
                "ontology": {"unit": "ratio_fraction", "concept": "FractionUnit"},
            },
            static_graph={"edges": [{"source": "broker_executor", "target": "pricing", "type": "STATIC_CALL"}]},
            runtime_traces=[{"client_service": "broker_executor", "target_service": "pricing", "call_count_7d": 11000}],
            ground_truth=GroundTruthFinding(
                finding_code="SEMANTIC_DRIFT_MONETARY_UNIT",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=True,
                expected_affected_entities=["broker_executor"],
                expected_impact_paths=[["broker_executor", "pricing"]],
                evidence_sources=["Ontology:OssieSoftwareOntology"],
                description="Basis points to fraction unit shift triggers 10,000x overcharging risk.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-13",
            name="Cryptocurrency Satoshi to Bitcoin unit shift",
            category=ScenarioCategory.MONETARY_UNIT_CHANGE,
            split=DatasetSplit.DEVELOPMENT,
            description="Crypto wallet service shifts payout amount from Satoshis (100,000,000) to BTC float.",
            changed_artifact="services/wallet/openapi.yaml",
            before_state={
                "properties": {"tx_value": {"type": "number"}},
                "ontology": {"unit": "satoshi", "concept": "CryptoSubunit"},
            },
            after_state={
                "properties": {"tx_value": {"type": "number"}},
                "ontology": {"unit": "btc", "concept": "CryptoMainUnit"},
            },
            static_graph={"edges": [{"source": "settlement_gateway", "target": "wallet", "type": "STATIC_CALL"}]},
            ground_truth=GroundTruthFinding(
                finding_code="SEMANTIC_DRIFT_MONETARY_UNIT",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=True,
                expected_affected_entities=["settlement_gateway"],
                expected_impact_paths=[["settlement_gateway", "wallet"]],
                evidence_sources=["Ontology:OssieSoftwareOntology"],
                description="Satoshi to BTC shift causes catastrophic magnitude errors.",
            ),
        )
    )

    # =========================================================================
    # Category 5: TIMESTAMP_INTERPRETATION_CHANGE (SCEN-14 .. SCEN-16)
    # =========================================================================
    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-14",
            name="Event timestamp Epoch Seconds to Milliseconds",
            category=ScenarioCategory.TIMESTAMP_INTERPRETATION_CHANGE,
            split=DatasetSplit.DEVELOPMENT,
            description="Telemetry event timestamp switches from Unix seconds to Unix milliseconds (both integers).",
            changed_artifact="services/telemetry/event_schema.json",
            before_state={
                "properties": {"timestamp": {"type": "integer"}},
                "ontology": {"time_format": "epoch_seconds", "concept": "TimeSeconds"},
            },
            after_state={
                "properties": {"timestamp": {"type": "integer"}},
                "ontology": {"time_format": "epoch_milliseconds", "concept": "TimeMilliseconds"},
            },
            static_graph={"edges": [{"source": "metrics_aggregator", "target": "telemetry", "type": "STATIC_CALL"}]},
            runtime_traces=[
                {"client_service": "metrics_aggregator", "target_service": "telemetry", "call_count_7d": 45000}
            ],
            ground_truth=GroundTruthFinding(
                finding_code="SEMANTIC_DRIFT_TIMESTAMP",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=True,
                expected_affected_entities=["metrics_aggregator"],
                expected_impact_paths=[["metrics_aggregator", "telemetry"]],
                evidence_sources=["Ontology:OssieSoftwareOntology"],
                description="1000x clock skew error renders time-series aggregation completely corrupt.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-15",
            name="Appointment expires_at UTC to Local Timezone",
            category=ScenarioCategory.TIMESTAMP_INTERPRETATION_CHANGE,
            split=DatasetSplit.DEVELOPMENT,
            description="Scheduling service changes timestamp interpretation from UTC Zulu to server local time.",
            changed_artifact="services/scheduler/openapi.yaml",
            before_state={
                "properties": {"expires_at": {"type": "string"}},
                "ontology": {"time_format": "ISO8601_UTC", "concept": "TimeUTC"},
            },
            after_state={
                "properties": {"expires_at": {"type": "string"}},
                "ontology": {"time_format": "ISO8601_LOCAL", "concept": "TimeLocal"},
            },
            static_graph={"edges": [{"source": "booking_client", "target": "scheduler", "type": "STATIC_CALL"}]},
            ground_truth=GroundTruthFinding(
                finding_code="SEMANTIC_DRIFT_TIMESTAMP",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=True,
                expected_affected_entities=["booking_client"],
                expected_impact_paths=[["booking_client", "scheduler"]],
                evidence_sources=["Ontology:OssieSoftwareOntology"],
                description="Timezone ambiguity causes premature appointment expiration.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-16",
            name="Session TTL Duration Minutes to Seconds",
            category=ScenarioCategory.TIMESTAMP_INTERPRETATION_CHANGE,
            split=DatasetSplit.HOLDOUT,
            description="Auth session duration integer changed from minutes to seconds.",
            changed_artifact="services/session/schema.json",
            before_state={
                "properties": {"ttl": {"type": "integer"}},
                "ontology": {"time_format": "duration_minutes", "concept": "DurationMinutes"},
            },
            after_state={
                "properties": {"ttl": {"type": "integer"}},
                "ontology": {"time_format": "duration_seconds", "concept": "DurationSeconds"},
            },
            static_graph={"edges": [{"source": "sso_gateway", "target": "session", "type": "STATIC_CALL"}]},
            runtime_traces=[{"client_service": "sso_gateway", "target_service": "session", "call_count_7d": 90000}],
            ground_truth=GroundTruthFinding(
                finding_code="SEMANTIC_DRIFT_TIMESTAMP",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=True,
                expected_affected_entities=["sso_gateway"],
                expected_impact_paths=[["sso_gateway", "session"]],
                evidence_sources=["Ontology:OssieSoftwareOntology"],
                description="60x session expiration truncation.",
            ),
        )
    )

    # =========================================================================
    # Category 6: IDENTIFIER_SEMANTIC_DRIFT (SCEN-17 .. SCEN-19)
    # =========================================================================
    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-17",
            name="customer_id Shifts from EndUser to TenantOrg",
            category=ScenarioCategory.IDENTIFIER_SEMANTIC_DRIFT,
            split=DatasetSplit.DEVELOPMENT,
            description="customer_id field name remains identical but semantic concept shifts from Individual User to Organization Tenant.",
            changed_artifact="services/crm/openapi.yaml",
            before_state={
                "properties": {"customer_id": {"type": "string"}},
                "ontology": {"concept": "IndividualPersonID"},
            },
            after_state={
                "properties": {"customer_id": {"type": "string"}},
                "ontology": {"concept": "EnterpriseTenantID"},
            },
            static_graph={"edges": [{"source": "support_portal", "target": "crm", "type": "STATIC_CALL"}]},
            runtime_traces=[{"client_service": "support_portal", "target_service": "crm", "call_count_7d": 14000}],
            ground_truth=GroundTruthFinding(
                finding_code="SEMANTIC_DRIFT_IDENTIFIER",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=True,
                expected_affected_entities=["support_portal"],
                expected_impact_paths=[["support_portal", "crm"]],
                evidence_sources=["Ontology:NvidiaAutoOntology"],
                description="Polysemous ID drift causes cross-tenant permission leak or lookup failure.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-18",
            name="device_id Shifts from HardwareMAC to AppInstanceGUID",
            category=ScenarioCategory.IDENTIFIER_SEMANTIC_DRIFT,
            split=DatasetSplit.DEVELOPMENT,
            description="Mobile push service redefines device_id from physical MAC to ephemeral App installation GUID.",
            changed_artifact="services/push/openapi.yaml",
            before_state={
                "properties": {"device_id": {"type": "string"}},
                "ontology": {"concept": "HardwareMACAddress"},
            },
            after_state={
                "properties": {"device_id": {"type": "string"}},
                "ontology": {"concept": "EphemeralAppInstallID"},
            },
            static_graph={"edges": [{"source": "notification_hub", "target": "push", "type": "STATIC_CALL"}]},
            ground_truth=GroundTruthFinding(
                finding_code="SEMANTIC_DRIFT_IDENTIFIER",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=True,
                expected_affected_entities=["notification_hub"],
                expected_impact_paths=[["notification_hub", "push"]],
                evidence_sources=["Ontology:OssieSoftwareOntology"],
                description="Token invalidation on reinstall unnoticed by notification hub.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-19",
            name="session_token Shifts from StatefulSession to StatelessJWT",
            category=ScenarioCategory.IDENTIFIER_SEMANTIC_DRIFT,
            split=DatasetSplit.HOLDOUT,
            description="Auth service redefines session_token from Redis opaque UUID to cryptographically signed compact JWT.",
            changed_artifact="services/auth/session.yaml",
            before_state={
                "properties": {"session_token": {"type": "string"}},
                "ontology": {"concept": "OpaqueRedisSessionKey"},
            },
            after_state={
                "properties": {"session_token": {"type": "string"}},
                "ontology": {"concept": "SignedCompactJWT"},
            },
            static_graph={"edges": [{"source": "web_proxy", "target": "auth", "type": "STATIC_CALL"}]},
            runtime_traces=[{"client_service": "web_proxy", "target_service": "auth", "call_count_7d": 80000}],
            ground_truth=GroundTruthFinding(
                finding_code="SEMANTIC_DRIFT_IDENTIFIER",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=True,
                expected_affected_entities=["web_proxy"],
                expected_impact_paths=[["web_proxy", "auth"]],
                evidence_sources=["Ontology:OssieSoftwareOntology"],
                description="Token size explosion and revocation strategy incompatibility.",
            ),
        )
    )

    # =========================================================================
    # Category 7: ENUM_SEMANTIC_CHANGES (SCEN-20 .. SCEN-22)
    # =========================================================================
    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-20",
            name="OrderStatus PENDING Replaced by INITIALIZING",
            category=ScenarioCategory.ENUM_SEMANTIC_CHANGES,
            split=DatasetSplit.DEVELOPMENT,
            description="OrderStatus enum replaces PENDING with INITIALIZING, breaking non-tolerant switch-case handlers.",
            changed_artifact="services/order/status.json",
            before_state={
                "properties": {"status": {"type": "string", "enum": ["PENDING", "COMPLETED", "FAILED"]}},
                "ontology": {"enum_meanings": {"PENDING": "awaiting_payment"}},
            },
            after_state={
                "properties": {"status": {"type": "string", "enum": ["INITIALIZING", "COMPLETED", "FAILED"]}},
                "ontology": {"enum_meanings": {"INITIALIZING": "draft_order_creation"}},
            },
            static_graph={"edges": [{"source": "payment_service", "target": "order", "type": "STATIC_CALL"}]},
            ground_truth=GroundTruthFinding(
                finding_code="SEMANTIC_DRIFT_ENUM",
                severity="WARNING",
                is_breaking=True,
                is_semantic_drift=True,
                expected_affected_entities=["payment_service"],
                expected_impact_paths=[["payment_service", "order"]],
                evidence_sources=["AST:services/order/status.json"],
                description="State machine enum value replacement causes unexpected default branch execution.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-21",
            name="ShipmentStatus Added AWAITING_CUSTOMS",
            category=ScenarioCategory.ENUM_SEMANTIC_CHANGES,
            split=DatasetSplit.DEVELOPMENT,
            description="Logistics adds new intermediate enum value AWAITING_CUSTOMS to shipment state enum.",
            changed_artifact="services/shipping/openapi.yaml",
            before_state={
                "properties": {"status": {"type": "string", "enum": ["PROCESSING", "SHIPPED", "DELIVERED"]}},
                "ontology": {"enum_meanings": {"state_count": 3}},
            },
            after_state={
                "properties": {
                    "status": {"type": "string", "enum": ["PROCESSING", "AWAITING_CUSTOMS", "SHIPPED", "DELIVERED"]}
                },
                "ontology": {"enum_meanings": {"state_count": 4}},
            },
            static_graph={"edges": [{"source": "customer_notifier", "target": "shipping", "type": "STATIC_CALL"}]},
            ground_truth=GroundTruthFinding(
                finding_code="SEMANTIC_DRIFT_ENUM",
                severity="WARNING",
                is_breaking=False,
                is_semantic_drift=True,
                expected_affected_entities=["customer_notifier"],
                expected_impact_paths=[["customer_notifier", "shipping"]],
                evidence_sources=["AST:services/shipping/openapi.yaml"],
                description="Unrecognized enum causes deserialization error in strict client parsers.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-22",
            name="RoleType Enum Values Converted to Lowercase",
            category=ScenarioCategory.ENUM_SEMANTIC_CHANGES,
            split=DatasetSplit.HOLDOUT,
            description="IAM switches RoleType from uppercase ['ADMIN', 'USER'] to lowercase ['admin', 'user'].",
            changed_artifact="services/iam/roles.json",
            before_state={
                "properties": {"role": {"type": "string", "enum": ["ADMIN", "USER"]}},
                "ontology": {"enum_meanings": {"case": "UPPERCASE"}},
            },
            after_state={
                "properties": {"role": {"type": "string", "enum": ["admin", "user"]}},
                "ontology": {"enum_meanings": {"case": "LOWERCASE"}},
            },
            static_graph={"edges": [{"source": "admin_console", "target": "iam", "type": "STATIC_CALL"}]},
            runtime_traces=[{"client_service": "admin_console", "target_service": "iam", "call_count_7d": 3500}],
            ground_truth=GroundTruthFinding(
                finding_code="SEMANTIC_DRIFT_ENUM",
                severity="WARNING",
                is_breaking=True,
                is_semantic_drift=True,
                expected_affected_entities=["admin_console"],
                expected_impact_paths=[["admin_console", "iam"]],
                evidence_sources=["AST:services/iam/roles.json"],
                description="Case-sensitive string comparisons in policy checkers fail.",
            ),
        )
    )

    # =========================================================================
    # Category 8: EVENT_SCHEMA_EVOLUTION (SCEN-23 .. SCEN-25)
    # =========================================================================
    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-23",
            name="Kafka OrderPlaced Event Drops items Array",
            category=ScenarioCategory.EVENT_SCHEMA_EVOLUTION,
            split=DatasetSplit.DEVELOPMENT,
            description="OrderPlaced message schema drops nested items array in favor of lazy query endpoint.",
            changed_artifact="events/OrderPlaced.json",
            before_state={"properties": {"order_id": {"type": "string"}, "items": {"type": "array"}}},
            after_state={"properties": {"order_id": {"type": "string"}}},
            static_graph={
                "edges": [{"source": "inventory_reserver", "target": "OrderPlaced", "type": "CONSUMES_EVENT"}]
            },
            runtime_traces=[
                {"client_service": "inventory_reserver", "target_service": "OrderPlaced", "call_count_7d": 32000}
            ],
            ground_truth=GroundTruthFinding(
                finding_code="FIELD_REMOVED",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["inventory_reserver"],
                expected_impact_paths=[["inventory_reserver", "OrderPlaced"]],
                evidence_sources=["AsyncAPI:events/OrderPlaced.json"],
                description="Event subscriber crashes upon missing items payload array.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-24",
            name="PaymentCompleted Event Type Changed from UUID to Int",
            category=ScenarioCategory.EVENT_SCHEMA_EVOLUTION,
            split=DatasetSplit.DEVELOPMENT,
            description="PaymentCompleted event switches payment_id from UUID string to integer.",
            changed_artifact="events/PaymentCompleted.json",
            before_state={"properties": {"payment_id": {"type": "string"}}},
            after_state={"properties": {"payment_id": {"type": "integer"}}},
            static_graph={
                "edges": [{"source": "receipt_generator", "target": "PaymentCompleted", "type": "CONSUMES_EVENT"}]
            },
            ground_truth=GroundTruthFinding(
                finding_code="TYPE_INCOMPATIBILITY",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["receipt_generator"],
                expected_impact_paths=[["receipt_generator", "PaymentCompleted"]],
                evidence_sources=["AsyncAPI:events/PaymentCompleted.json"],
                description="Event subscriber deserialization type mismatch.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-25",
            name="UserRegistered Event Envelope Structure Flattened",
            category=ScenarioCategory.EVENT_SCHEMA_EVOLUTION,
            split=DatasetSplit.HOLDOUT,
            description="Event bus drops outer metadata envelope {data: {user_id: ...}} directly exposing {user_id: ...}.",
            changed_artifact="events/UserRegistered.json",
            before_state={"properties": {"data": {"type": "object"}}},
            after_state={"properties": {"user_id": {"type": "string"}}},
            static_graph={
                "edges": [{"source": "welcome_email_worker", "target": "UserRegistered", "type": "CONSUMES_EVENT"}]
            },
            runtime_traces=[
                {"client_service": "welcome_email_worker", "target_service": "UserRegistered", "call_count_7d": 7200}
            ],
            ground_truth=GroundTruthFinding(
                finding_code="FIELD_REMOVED",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["welcome_email_worker"],
                expected_impact_paths=[["welcome_email_worker", "UserRegistered"]],
                evidence_sources=["AsyncAPI:events/UserRegistered.json"],
                description="Envelope removal breaks subscriber message unwrapping.",
            ),
        )
    )

    # =========================================================================
    # Category 9: EVENT_ORDERING_ISSUES (SCEN-26 .. SCEN-28)
    # =========================================================================
    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-26",
            name="Kafka Topic Partitioning Changed from OrderID to Random",
            category=ScenarioCategory.EVENT_ORDERING_ISSUES,
            split=DatasetSplit.DEVELOPMENT,
            description="Kafka producer switches message key from order_id to random UUID, destroying per-order FIFO ordering.",
            changed_artifact="services/order/kafka_producer.yaml",
            before_state={"delivery_order": "FIFO_STRICT", "partition_key": "order_id"},
            after_state={"delivery_order": "UNORDERED", "partition_key": "random_uuid"},
            static_graph={
                "edges": [{"source": "order_state_machine", "target": "kafka_producer", "type": "STATIC_CALL"}]
            },
            ground_truth=GroundTruthFinding(
                finding_code="EVENT_ORDERING_ASSUMPTION_VIOLATED",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["order_state_machine"],
                expected_impact_paths=[["order_state_machine", "kafka_producer"]],
                evidence_sources=["AsyncAPI:services/order/kafka_producer.yaml"],
                description="Out-of-order event delivery triggers race conditions in state machine.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-27",
            name="Payment SQS Queue Switched from FIFO to Standard",
            category=ScenarioCategory.EVENT_ORDERING_ISSUES,
            split=DatasetSplit.DEVELOPMENT,
            description="AWS SQS queue upgraded/downgraded from FIFO to Standard, losing strictly once & ordering guarantees.",
            changed_artifact="infra/sqs_payment.yaml",
            before_state={"delivery_order": "FIFO_STRICT", "deduplication": True},
            after_state={"delivery_order": "UNORDERED", "deduplication": False},
            static_graph={"edges": [{"source": "ledger_service", "target": "sqs_payment", "type": "STATIC_CALL"}]},
            ground_truth=GroundTruthFinding(
                finding_code="EVENT_ORDERING_ASSUMPTION_VIOLATED",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["ledger_service"],
                expected_impact_paths=[["ledger_service", "sqs_payment"]],
                evidence_sources=["Infra:infra/sqs_payment.yaml"],
                description="Standard queue allows duplicate and out-of-order execution.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-28",
            name="Workflow Engine Asynchronous Step Parallelization",
            category=ScenarioCategory.EVENT_ORDERING_ISSUES,
            split=DatasetSplit.HOLDOUT,
            description="Workflow engine executes charge_card and reserve_inventory in parallel instead of sequentially.",
            changed_artifact="workflows/order_fulfillment.json",
            before_state={"delivery_order": "SEQUENTIAL_STRICT"},
            after_state={"delivery_order": "UNORDERED"},
            static_graph={
                "edges": [{"source": "inventory_service", "target": "order_fulfillment", "type": "WORKFLOW_STEP"}]
            },
            runtime_traces=[
                {"client_service": "inventory_service", "target_service": "order_fulfillment", "call_count_7d": 19000}
            ],
            ground_truth=GroundTruthFinding(
                finding_code="EVENT_ORDERING_ASSUMPTION_VIOLATED",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["inventory_service"],
                expected_impact_paths=[["inventory_service", "order_fulfillment"]],
                evidence_sources=["Workflow:workflows/order_fulfillment.json"],
                description="Inventory reserved for transactions that subsequently fail authorization.",
            ),
        )
    )

    # =========================================================================
    # Category 10: DATABASE_MIGRATION_IMPACT (SCEN-29 .. SCEN-32)
    # =========================================================================
    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-29",
            name="PostgreSQL Migration Drops orders.customer_id Column",
            category=ScenarioCategory.DATABASE_MIGRATION_IMPACT,
            split=DatasetSplit.DEVELOPMENT,
            description="Alembic DDL migration drops column customer_id while active read queries still reference it.",
            changed_artifact="migrations/004_drop_customer_id.sql",
            before_state={"columns": {"id": {"type": "UUID"}, "customer_id": {"type": "UUID"}}},
            after_state={"columns": {"id": {"type": "UUID"}}},
            static_graph={"edges": [{"source": "orders_api", "target": "migrations", "type": "SQL_QUERY"}]},
            runtime_traces=[{"client_service": "orders_api", "target_service": "migrations", "call_count_7d": 65000}],
            ground_truth=GroundTruthFinding(
                finding_code="DATABASE_COLUMN_DROPPED",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["orders_api"],
                expected_impact_paths=[["orders_api", "migrations"]],
                evidence_sources=["SQL:migrations/004_drop_customer_id.sql"],
                description="Query SELECT customer_id FROM orders fails immediately.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-30",
            name="Adding Non-Nullable Column Without Default Value",
            category=ScenarioCategory.DATABASE_MIGRATION_IMPACT,
            split=DatasetSplit.DEVELOPMENT,
            description="Migration adds mandatory column tax_code NOT NULL without DEFAULT, failing legacy INSERT statements.",
            changed_artifact="migrations/005_add_tax_code.sql",
            before_state={"columns": {"id": {"type": "UUID"}}},
            after_state={
                "columns": {
                    "id": {"type": "UUID"},
                    "tax_code": {"type": "VARCHAR(20)", "nullable": False, "default": None},
                }
            },
            static_graph={"edges": [{"source": "cart_checkout", "target": "migrations", "type": "SQL_QUERY"}]},
            ground_truth=GroundTruthFinding(
                finding_code="DATABASE_NON_NULLABLE_NO_DEFAULT",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["cart_checkout"],
                expected_impact_paths=[["cart_checkout", "migrations"]],
                evidence_sources=["SQL:migrations/005_add_tax_code.sql"],
                description="NOT NULL constraint violation on legacy INSERTs.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-31",
            name="PostgreSQL Column Type VARCHAR(50) Changed to UUID",
            category=ScenarioCategory.DATABASE_MIGRATION_IMPACT,
            split=DatasetSplit.HOLDOUT,
            description="Migration changes external_reference from VARCHAR(50) to strict UUID, rejecting legacy non-UUID formats.",
            changed_artifact="migrations/006_alter_ref.sql",
            before_state={"columns": {"external_reference": {"type": "VARCHAR(50)"}}},
            after_state={"columns": {"external_reference": {"type": "UUID"}}},
            static_graph={"edges": [{"source": "legacy_partner_sync", "target": "migrations", "type": "SQL_QUERY"}]},
            runtime_traces=[
                {"client_service": "legacy_partner_sync", "target_service": "migrations", "call_count_7d": 8500}
            ],
            ground_truth=GroundTruthFinding(
                finding_code="TYPE_INCOMPATIBILITY",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["legacy_partner_sync"],
                expected_impact_paths=[["legacy_partner_sync", "migrations"]],
                evidence_sources=["SQL:migrations/006_alter_ref.sql"],
                description="Invalid input syntax for type uuid on non-UUID strings.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-32",
            name="Dropping Foreign Key Constraint and Index",
            category=ScenarioCategory.DATABASE_MIGRATION_IMPACT,
            split=DatasetSplit.DEVELOPMENT,
            description="Migration drops foreign key index leading to sequential table scan and connection pool starvation.",
            changed_artifact="migrations/007_drop_fk.sql",
            before_state={"columns": {"order_id_fk": {"type": "UUID"}}},
            after_state={"columns": {}},
            static_graph={"edges": [{"source": "analytics_query_engine", "target": "migrations", "type": "SQL_QUERY"}]},
            ground_truth=GroundTruthFinding(
                finding_code="DATABASE_COLUMN_DROPPED",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["analytics_query_engine"],
                expected_impact_paths=[["analytics_query_engine", "migrations"]],
                evidence_sources=["SQL:migrations/007_drop_fk.sql"],
                description="Database constraint and column dropped.",
            ),
        )
    )

    # =========================================================================
    # Category 11: HIDDEN_DOWNSTREAM_CONSUMERS (SCEN-33 .. SCEN-35)
    # =========================================================================
    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-33",
            name="Nightly Batch Billing Worker Undocumented Endpoint Consumer",
            category=ScenarioCategory.HIDDEN_DOWNSTREAM_CONSUMERS,
            split=DatasetSplit.DEVELOPMENT,
            description="An unindexed cron job billing_batch_worker calls an undocumented /internal/accounts route dropped in PR.",
            changed_artifact="services/account/openapi.yaml",
            before_state={"paths": {"/internal/accounts": {"methods": ["GET"]}}},
            after_state={"paths": {}},
            static_graph={"edges": []},  # NOT found in static code imports!
            runtime_traces=[
                {"client_service": "billing_batch_worker", "target_service": "account", "call_count_7d": 100}
            ],
            ground_truth=GroundTruthFinding(
                finding_code="ENDPOINT_REMOVED",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["billing_batch_worker"],
                expected_impact_paths=[["billing_batch_worker", "account"]],
                evidence_sources=["OTel:billing_batch_worker->account", "AST:services/account/openapi.yaml"],
                description="Hidden batch worker discovered solely through OpenTelemetry runtime traces.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-34",
            name="Data Engineering ETL Pipeline Consuming Direct Internal Route",
            category=ScenarioCategory.HIDDEN_DOWNSTREAM_CONSUMERS,
            split=DatasetSplit.DEVELOPMENT,
            description="ETL spark streaming pipeline extracts raw events via internal route deleted in refactoring.",
            changed_artifact="services/events/openapi.yaml",
            before_state={"paths": {"/stream/raw": {"methods": ["GET"]}}},
            after_state={"paths": {}},
            static_graph={"edges": []},
            runtime_traces=[
                {"client_service": "spark_etl_pipeline", "target_service": "events", "call_count_7d": 54000}
            ],
            ground_truth=GroundTruthFinding(
                finding_code="ENDPOINT_REMOVED",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["spark_etl_pipeline"],
                expected_impact_paths=[["spark_etl_pipeline", "events"]],
                evidence_sources=["OTel:spark_etl_pipeline->events"],
                description="Static analysis misses ETL client; runtime OTel catches live streaming calls.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-35",
            name="Regulatory Compliance Audit Exporter Consumer",
            category=ScenarioCategory.HIDDEN_DOWNSTREAM_CONSUMERS,
            split=DatasetSplit.HOLDOUT,
            description="SOC2 audit collector script polls /audit/trail endpoint removed during API modernization.",
            changed_artifact="services/audit/openapi.yaml",
            before_state={"paths": {"/audit/trail": {"methods": ["GET"]}}},
            after_state={"paths": {}},
            static_graph={"edges": []},
            runtime_traces=[{"client_service": "soc2_audit_collector", "target_service": "audit", "call_count_7d": 50}],
            ground_truth=GroundTruthFinding(
                finding_code="ENDPOINT_REMOVED",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["soc2_audit_collector"],
                expected_impact_paths=[["soc2_audit_collector", "audit"]],
                evidence_sources=["OTel:soc2_audit_collector->audit"],
                description="Low-frequency but critical compliance exporter broken.",
            ),
        )
    )

    # =========================================================================
    # Category 12: TRANSITIVE_SERVICE_DEPENDENCIES (SCEN-36 .. SCEN-39)
    # =========================================================================
    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-36",
            name="3-Hop Transitive Cascade: Auth -> User -> Order -> Frontend",
            category=ScenarioCategory.TRANSITIVE_SERVICE_DEPENDENCIES,
            split=DatasetSplit.DEVELOPMENT,
            description="Breaking field removal in Auth service propagates 3 hops downstream to Frontend Web App.",
            changed_artifact="services/auth/openapi.yaml",
            before_state={"properties": {"session_id": {"type": "string"}}},
            after_state={"properties": {}},
            static_graph={
                "edges": [
                    {"source": "user_service", "target": "auth", "type": "STATIC_CALL"},
                    {"source": "order_service", "target": "user_service", "type": "STATIC_CALL"},
                    {"source": "web_frontend", "target": "order_service", "type": "STATIC_CALL"},
                ]
            },
            runtime_traces=[
                {"client_service": "user_service", "target_service": "auth", "call_count_7d": 50000},
                {"client_service": "order_service", "target_service": "user_service", "call_count_7d": 40000},
                {"client_service": "web_frontend", "target_service": "order_service", "call_count_7d": 30000},
            ],
            ground_truth=GroundTruthFinding(
                finding_code="FIELD_REMOVED",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["user_service", "order_service", "web_frontend"],
                expected_impact_paths=[
                    ["user_service", "auth"],
                    ["order_service", "user_service", "auth"],
                    ["web_frontend", "order_service", "user_service", "auth"],
                ],
                evidence_sources=["AST:services/auth/openapi.yaml", "Graph:3-hop-traversal"],
                description="Cascading transitive failure across 3 microservice boundaries.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-37",
            name="4-Hop Inventory Cascade to External Courier Dispatch",
            category=ScenarioCategory.TRANSITIVE_SERVICE_DEPENDENCIES,
            split=DatasetSplit.DEVELOPMENT,
            description="Field removal in Inventory cascades through Warehouse, Fulfillment, and Courier Dispatcher.",
            changed_artifact="services/inventory/openapi.yaml",
            before_state={"properties": {"bin_location": {"type": "string"}}},
            after_state={"properties": {}},
            static_graph={
                "edges": [
                    {"source": "warehouse_srv", "target": "inventory", "type": "STATIC_CALL"},
                    {"source": "fulfillment_srv", "target": "warehouse_srv", "type": "STATIC_CALL"},
                    {"source": "courier_dispatcher", "target": "fulfillment_srv", "type": "STATIC_CALL"},
                ]
            },
            ground_truth=GroundTruthFinding(
                finding_code="FIELD_REMOVED",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["warehouse_srv", "fulfillment_srv", "courier_dispatcher"],
                expected_impact_paths=[["courier_dispatcher", "fulfillment_srv", "warehouse_srv", "inventory"]],
                evidence_sources=["AST:services/inventory/openapi.yaml"],
                description="Deep 4-tier fulfillment chain failure.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-38",
            name="Transitive Payment Core to Partner Affiliate Settlement",
            category=ScenarioCategory.TRANSITIVE_SERVICE_DEPENDENCIES,
            split=DatasetSplit.HOLDOUT,
            description="Payment core removes payout_token impacting Affiliate Service via Ledger and Settlement gateways.",
            changed_artifact="services/payment_core/openapi.yaml",
            before_state={"properties": {"payout_token": {"type": "string"}}},
            after_state={"properties": {}},
            static_graph={
                "edges": [
                    {"source": "ledger_service", "target": "payment_core", "type": "STATIC_CALL"},
                    {"source": "settlement_gw", "target": "ledger_service", "type": "STATIC_CALL"},
                    {"source": "affiliate_payout", "target": "settlement_gw", "type": "STATIC_CALL"},
                ]
            },
            ground_truth=GroundTruthFinding(
                finding_code="FIELD_REMOVED",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["ledger_service", "settlement_gw", "affiliate_payout"],
                expected_impact_paths=[["affiliate_payout", "settlement_gw", "ledger_service", "payment_core"]],
                evidence_sources=["AST:services/payment_core/openapi.yaml"],
                description="B2B partner affiliate payout broken by transitive contract removal.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-39",
            name="Multi-Branch Fan-Out Transitive Dependency",
            category=ScenarioCategory.TRANSITIVE_SERVICE_DEPENDENCIES,
            split=DatasetSplit.DEVELOPMENT,
            description="Common Core Utility removes encrypt_payload impacting two independent service branches.",
            changed_artifact="services/crypto_core/openapi.yaml",
            before_state={"properties": {"cipher_mode": {"type": "string"}}},
            after_state={"properties": {}},
            static_graph={
                "edges": [
                    {"source": "card_vault", "target": "crypto_core", "type": "STATIC_CALL"},
                    {"source": "pii_sanitizer", "target": "crypto_core", "type": "STATIC_CALL"},
                ]
            },
            ground_truth=GroundTruthFinding(
                finding_code="FIELD_REMOVED",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["card_vault", "pii_sanitizer"],
                expected_impact_paths=[["card_vault", "crypto_core"], ["pii_sanitizer", "crypto_core"]],
                evidence_sources=["AST:services/crypto_core/openapi.yaml"],
                description="Fan-out impact across both security vault and compliance sanitizer.",
            ),
        )
    )

    # =========================================================================
    # Category 13: RUNTIME_ONLY_DEPENDENCIES (SCEN-40 .. SCEN-42)
    # =========================================================================
    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-40",
            name="Dynamic Consul Service Discovery Dynamic RPC",
            category=ScenarioCategory.RUNTIME_ONLY_DEPENDENCIES,
            split=DatasetSplit.DEVELOPMENT,
            description="Dynamic service invocation resolved via Consul registry at runtime with zero static imports.",
            changed_artifact="services/pricing_calculator/openapi.yaml",
            before_state={"properties": {"surge_multiplier": {"type": "number"}}},
            after_state={"properties": {}},
            static_graph={"edges": []},  # Completely absent from static code AST!
            runtime_traces=[
                {
                    "client_service": "ride_dispatch_engine",
                    "target_service": "pricing_calculator",
                    "call_count_7d": 120000,
                }
            ],
            ground_truth=GroundTruthFinding(
                finding_code="FIELD_REMOVED",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["ride_dispatch_engine"],
                expected_impact_paths=[["ride_dispatch_engine", "pricing_calculator"]],
                evidence_sources=["OTel:ride_dispatch_engine->pricing_calculator"],
                description="Runtime-only dynamic RPC discovered strictly via OpenTelemetry spans.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-41",
            name="Cross-Cluster RabbitMQ Topic Runtime Consumer",
            category=ScenarioCategory.RUNTIME_ONLY_DEPENDENCIES,
            split=DatasetSplit.DEVELOPMENT,
            description="Cross-cluster message queue consumer with dynamic routing keys unresolvable by static AST.",
            changed_artifact="services/geo_tracking/schema.json",
            before_state={"properties": {"latitude": {"type": "number"}, "longitude": {"type": "number"}}},
            after_state={"properties": {"coords": {"type": "array"}}},
            static_graph={"edges": []},
            runtime_traces=[
                {"client_service": "fleet_map_dashboard", "target_service": "geo_tracking", "call_count_7d": 78000}
            ],
            ground_truth=GroundTruthFinding(
                finding_code="FIELD_REMOVED",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["fleet_map_dashboard"],
                expected_impact_paths=[["fleet_map_dashboard", "geo_tracking"]],
                evidence_sources=["OTel:fleet_map_dashboard->geo_tracking"],
                description="Runtime telemetry reveals real-time fleet map depends on coordinates.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-42",
            name="Polyglot gRPC Reflection Dynamic Invocation",
            category=ScenarioCategory.RUNTIME_ONLY_DEPENDENCIES,
            split=DatasetSplit.HOLDOUT,
            description="Go gateway invokes Python ML model dynamically via gRPC Server Reflection without compiled proto stubs.",
            changed_artifact="services/ml_recommender/proto.json",
            before_state={"properties": {"user_vector": {"type": "array"}}},
            after_state={"properties": {"embeddings": {"type": "array"}}},
            static_graph={"edges": []},
            runtime_traces=[
                {"client_service": "recommendation_edge_gw", "target_service": "ml_recommender", "call_count_7d": 95000}
            ],
            ground_truth=GroundTruthFinding(
                finding_code="FIELD_REMOVED",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["recommendation_edge_gw"],
                expected_impact_paths=[["recommendation_edge_gw", "ml_recommender"]],
                evidence_sources=["OTel:recommendation_edge_gw->ml_recommender"],
                description="Reflection-based dynamic invocation only visible in OTel traces.",
            ),
        )
    )

    # =========================================================================
    # Category 14: PERMISSION_CHANGES (SCEN-43 .. SCEN-45)
    # =========================================================================
    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-43",
            name="OAuth Scope Escalation: read:users to admin:users",
            category=ScenarioCategory.PERMISSION_CHANGES,
            split=DatasetSplit.DEVELOPMENT,
            description="User endpoint tightens required OAuth scope from read:users to admin:users, locking out service token.",
            changed_artifact="services/user_mgmt/security.yaml",
            before_state={"required_permissions": ["read:users"]},
            after_state={"required_permissions": ["admin:users"]},
            static_graph={"edges": [{"source": "dashboard_backend", "target": "user_mgmt", "type": "STATIC_CALL"}]},
            ground_truth=GroundTruthFinding(
                finding_code="PERMISSION_REQUIREMENT_ESCALATED",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["dashboard_backend"],
                expected_impact_paths=[["dashboard_backend", "user_mgmt"]],
                evidence_sources=["AST:services/user_mgmt/security.yaml"],
                description="Service client possessing only read:users receives 403 Forbidden.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-44",
            name="mTLS Client Certificate Authorization Policy Added",
            category=ScenarioCategory.PERMISSION_CHANGES,
            split=DatasetSplit.DEVELOPMENT,
            description="Internal payment RPC endpoint adds strict mTLS client SAN identity requirement.",
            changed_artifact="services/secure_payout/authz.json",
            before_state={"required_permissions": []},
            after_state={"required_permissions": ["spiffe://acme.org/ns/prod/sa/trusted-payout"]},
            static_graph={
                "edges": [{"source": "batch_payout_runner", "target": "secure_payout", "type": "STATIC_CALL"}]
            },
            ground_truth=GroundTruthFinding(
                finding_code="PERMISSION_REQUIREMENT_ESCALATED",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["batch_payout_runner"],
                expected_impact_paths=[["batch_payout_runner", "secure_payout"]],
                evidence_sources=["SecurityPolicy:services/secure_payout/authz.json"],
                description="Client rejected with 401/403 missing mTLS principal.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-45",
            name="Role-Based Gating Added to Document Download Endpoint",
            category=ScenarioCategory.PERMISSION_CHANGES,
            split=DatasetSplit.HOLDOUT,
            description="Document retrieval endpoint requires COMPLIANCE_OFFICER role in JWT claim.",
            changed_artifact="services/docs/routes.json",
            before_state={"required_permissions": ["VIEWER"]},
            after_state={"required_permissions": ["COMPLIANCE_OFFICER"]},
            static_graph={"edges": [{"source": "customer_support_app", "target": "docs", "type": "STATIC_CALL"}]},
            runtime_traces=[
                {"client_service": "customer_support_app", "target_service": "docs", "call_count_7d": 6200}
            ],
            ground_truth=GroundTruthFinding(
                finding_code="PERMISSION_REQUIREMENT_ESCALATED",
                severity="BLOCKING",
                is_breaking=True,
                is_semantic_drift=False,
                expected_affected_entities=["customer_support_app"],
                expected_impact_paths=[["customer_support_app", "docs"]],
                evidence_sources=["AST:services/docs/routes.json"],
                description="Support agents locked out of customer invoice viewing.",
            ),
        )
    )

    # =========================================================================
    # Category 15: UNRELATED_CHANGES (SCEN-46 .. SCEN-52) - Negative Controls
    # =========================================================================
    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-46",
            name="Documentation Update in README.md",
            category=ScenarioCategory.UNRELATED_CHANGES,
            split=DatasetSplit.DEVELOPMENT,
            description="Developer updates markdown formatting and setup instructions in repository README.md.",
            changed_artifact="README.md",
            before_state={"content": "# Old Documentation"},
            after_state={"content": "# Modernized Documentation with Examples"},
            static_graph={"edges": []},
            ground_truth=GroundTruthFinding(
                finding_code="NO_BREAKING_CHANGES",
                severity="NONE",
                is_breaking=False,
                is_semantic_drift=False,
                expected_affected_entities=[],
                expected_impact_paths=[],
                evidence_sources=["Diff:README.md"],
                description="Pure documentation edit; zero production impact.",
            ),
            expected_non_findings=["FIELD_REMOVED", "TYPE_INCOMPATIBILITY", "SEMANTIC_DRIFT_MONETARY_UNIT"],
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-47",
            name="Internal Helper Function Refactoring (Private Scope)",
            category=ScenarioCategory.UNRELATED_CHANGES,
            split=DatasetSplit.DEVELOPMENT,
            description="Refactoring internal private function _compute_hash inside utility module without signature change.",
            changed_artifact="packages/shared/utils.py",
            before_state={"properties": {"_hash": {"type": "string"}}},
            after_state={"properties": {"_hash": {"type": "string"}}},
            static_graph={"edges": [{"source": "order_service", "target": "utils", "type": "INTERNAL_IMPORT"}]},
            ground_truth=GroundTruthFinding(
                finding_code="NO_BREAKING_CHANGES",
                severity="NONE",
                is_breaking=False,
                is_semantic_drift=False,
                expected_affected_entities=[],
                expected_impact_paths=[],
                evidence_sources=["AST:packages/shared/utils.py"],
                description="Private function optimization maintains identical public contracts.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-48",
            name="Adding Optional Non-Required Field with Default Value",
            category=ScenarioCategory.UNRELATED_CHANGES,
            split=DatasetSplit.DEVELOPMENT,
            description="Adding optional metadata field with default null value in additive, non-breaking fashion.",
            changed_artifact="services/order/openapi.yaml",
            before_state={"properties": {"order_id": {"type": "string"}}, "required": ["order_id"]},
            after_state={
                "properties": {"order_id": {"type": "string"}, "notes": {"type": "string"}},
                "required": ["order_id"],
            },
            static_graph={"edges": [{"source": "frontend_app", "target": "order", "type": "STATIC_CALL"}]},
            ground_truth=GroundTruthFinding(
                finding_code="NO_BREAKING_CHANGES",
                severity="NONE",
                is_breaking=False,
                is_semantic_drift=False,
                expected_affected_entities=[],
                expected_impact_paths=[],
                evidence_sources=["AST:services/order/openapi.yaml"],
                description="Additive optional expansion preserves full backwards compatibility.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-49",
            name="Unit Test Suite Additions",
            category=ScenarioCategory.UNRELATED_CHANGES,
            split=DatasetSplit.HOLDOUT,
            description="Adding new unit tests in tests/unit/test_payment.py without touching service implementation.",
            changed_artifact="tests/unit/test_payment.py",
            before_state={"content": "def test_old(): pass"},
            after_state={"content": "def test_old(): pass\ndef test_new(): pass"},
            static_graph={"edges": []},
            ground_truth=GroundTruthFinding(
                finding_code="NO_BREAKING_CHANGES",
                severity="NONE",
                is_breaking=False,
                is_semantic_drift=False,
                expected_affected_entities=[],
                expected_impact_paths=[],
                evidence_sources=["Diff:tests/unit/test_payment.py"],
                description="Test suite additions do not alter runtime contracts.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-50",
            name="CI/CD GitHub Actions Workflow Formatting",
            category=ScenarioCategory.UNRELATED_CHANGES,
            split=DatasetSplit.DEVELOPMENT,
            description="Updating CI timeout parameter and node version in .github/workflows/ci.yml.",
            changed_artifact=".github/workflows/ci.yml",
            before_state={"timeout_minutes": 20},
            after_state={"timeout_minutes": 25},
            static_graph={"edges": []},
            ground_truth=GroundTruthFinding(
                finding_code="NO_BREAKING_CHANGES",
                severity="NONE",
                is_breaking=False,
                is_semantic_drift=False,
                expected_affected_entities=[],
                expected_impact_paths=[],
                evidence_sources=["Diff:.github/workflows/ci.yml"],
                description="CI pipeline configuration change does not alter distributed contracts.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-51",
            name="Docker Compose Port Forwarding Update (Dev Environment Only)",
            category=ScenarioCategory.UNRELATED_CHANGES,
            split=DatasetSplit.HOLDOUT,
            description="Updating local docker-compose exposed debug port from 5432 to 5433.",
            changed_artifact="docker-compose.dev.yml",
            before_state={"port": 5432},
            after_state={"port": 5433},
            static_graph={"edges": []},
            ground_truth=GroundTruthFinding(
                finding_code="NO_BREAKING_CHANGES",
                severity="NONE",
                is_breaking=False,
                is_semantic_drift=False,
                expected_affected_entities=[],
                expected_impact_paths=[],
                evidence_sources=["Diff:docker-compose.dev.yml"],
                description="Local container port mapping has zero impact on distributed production contracts.",
            ),
        )
    )

    scenarios.append(
        BenchmarkScenario(
            scenario_id="SCEN-52",
            name="Log Formatting and Debug Log Additions",
            category=ScenarioCategory.UNRELATED_CHANGES,
            split=DatasetSplit.HOLDOUT,
            description="Adding structured log statements logger.debug('order_payload_received') inside handler.",
            changed_artifact="services/order/handler.py",
            before_state={"log_level": "INFO"},
            after_state={"log_level": "DEBUG"},
            static_graph={"edges": [{"source": "api_gateway", "target": "order", "type": "STATIC_CALL"}]},
            ground_truth=GroundTruthFinding(
                finding_code="NO_BREAKING_CHANGES",
                severity="NONE",
                is_breaking=False,
                is_semantic_drift=False,
                expected_affected_entities=[],
                expected_impact_paths=[],
                evidence_sources=["Diff:services/order/handler.py"],
                description="Internal logging changes must never trigger contract breakages or downstream alerts.",
            ),
        )
    )

    return scenarios
