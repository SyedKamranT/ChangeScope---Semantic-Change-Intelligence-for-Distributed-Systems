import { test, expect } from '@playwright/test'

test.describe('ChangeScope E2E Integration Suite', () => {
  test('Overview Dashboard renders real metrics, alert banner, and recent scans', async ({ page }) => {
    await page.goto('/')

    // Check title and brand
    await expect(page.getByText('ChangeScope')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'System Intelligence Overview' })).toBeVisible()

    // Verify Alert Banner for PR #142
    await expect(page.getByText('High-Risk Semantic Breaking Change Detected in PR #142')).toBeVisible()

    // Verify Stat Cards
    await expect(page.getByText('Registered Repositories')).toBeVisible()
    await expect(page.getByText('Contract Scans Executed')).toBeVisible()
    await expect(page.getByText('Detected Violations')).toBeVisible()
    await expect(page.getByText('OTel Observed Dependencies')).toBeVisible()

    // Verify Recent Scans Table
    await expect(page.getByText('Recent Change Analyses')).toBeVisible()
    await expect(page.getByText('inventory-service').first()).toBeVisible()
  })

  test('Repository Management supports search, filtering, and SSRF prevention guard', async ({ page }) => {
    await page.goto('/')

    // Navigate to Repositories
    await page.getByRole('button', { name: 'Repositories' }).click()
    await expect(page.getByRole('heading', { name: 'Repository Management' })).toBeVisible()

    // Search filter
    const searchInput = page.getByPlaceholder('Search repositories...')
    await searchInput.fill('checkout')
    await expect(page.getByText('checkout-service', { exact: true })).toBeVisible()
    await expect(page.getByText('inventory-service', { exact: true })).not.toBeVisible()

    // Clear search
    await searchInput.fill('')

    // Open Register Repository Modal
    await page.getByRole('button', { name: 'Register Repository' }).click()
    await expect(page.getByText('Connect a Git repository for automated AST extraction')).toBeVisible()

    // Try SSRF payload
    await page.getByLabel('Repository Name').fill('malicious-probe')
    await page.getByLabel('Git Clone URL (HTTPS)').fill('http://169.254.169.254/latest/meta-data')
    await page.getByRole('button', { name: 'Register & Extract Symbols' }).click()

    // Expect SSRF Guard rejection error
    await expect(page.getByText(/SSRF Protection Guard/i)).toBeVisible()
  })

  test('Pull Request Analysis verifies PR #142 breaking contract violations and PR #143 safe scenario', async ({
    page,
  }) => {
    await page.goto('/')
    await page.getByRole('button', { name: /Pull Request Review/i }).click()

    // Verify PR 142 is selected by default with violations
    await expect(page.getByText(/PR #142: Refactor inventory item status/i)).toBeVisible()
    await expect(page.getByText('RULE_ENUM_NARROWED')).toBeVisible()
    await expect(page.getByText('RULE_CLOSED_WORLD_COLLISION')).toBeVisible()
    await expect(page.getByText('RULE_DDL_COLUMN_SHRUNK')).toBeVisible()

    // Verify Diff Snippet
    await expect(page.getByText('-    CANCELLED = "CANCELLED"')).toBeVisible()

    // Switch to Safe PR 143
    await page.getByRole('button', { name: 'PR #143 (Safe)' }).click()
    await expect(page.getByText('Clean Contract Evolution')).toBeVisible()
    await expect(page.getByText('No breaking contract breaches')).toBeVisible()
  })

  test('Change Impact Explorer renders interactive graph, supports node inspection drawer', async ({
    page,
  }) => {
    await page.goto('/')
    await page.getByRole('button', { name: /Change Impact Explorer/i }).click()

    await expect(page.getByRole('heading', { name: 'Change Impact Explorer' })).toBeVisible()
    await expect(page.getByText('Interactive Blast Radius DAG')).toBeVisible()

    // Click on inventory-service node on graph canvas
    const inventoryNode = page.locator('.react-flow__node').filter({ hasText: 'inventory-service' })
    await expect(inventoryNode).toBeVisible()
    await inventoryNode.click()

    // Node Detail Drawer should slide in
    await expect(page.getByText('urn:changescope:service:srv-inventory')).toBeVisible()
    await expect(page.getByText('OpenTelemetry Observed Traffic')).toBeVisible()
    await expect(page.getByText('Verified Evidence Grounding')).toBeVisible()

    // Close drawer
    await page.getByLabel('Close drawer').click()
    await expect(page.getByText('urn:changescope:service:srv-inventory')).not.toBeVisible()
  })

  test('Semantic Drift Findings displays before/after definition differences', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: /Semantic Drift Findings/i }).click()

    await expect(page.getByRole('heading', { name: /Semantic Drift & Meaning Collisions/i })).toBeVisible()
    await expect(page.getByText('ENUM_NARROWED').first()).toBeVisible()
    await expect(page.getByText('UNIT_SHIFT')).toBeVisible()
    await expect(page.getByText('Before (Base Contract)').first()).toBeVisible()
    await expect(page.getByText('After (Proposed Drift)').first()).toBeVisible()
  })

  test('Runtime Topology verifies OpenTelemetry protocols and sampling invariant notice', async ({
    page,
  }) => {
    await page.goto('/')
    await page.getByRole('button', { name: /Runtime Topology \(OTel\)/i }).click()

    await expect(page.getByRole('heading', { name: /Runtime Dependency Intelligence/i })).toBeVisible()
    await expect(page.getByText('Permanent Grounding Invariant:')).toBeVisible()

    // Filter by KAFKA
    await page.getByRole('button', { name: 'KAFKA' }).click()
    await expect(page.getByRole('cell', { name: 'inventory-service' }).first()).toBeVisible()
    await expect(page.getByRole('cell', { name: 'analytics-pipeline' }).first()).toBeVisible()
    await expect(page.getByRole('cell', { name: 'checkout-service' })).not.toBeVisible()
  })

  test('Ontology Explorer displays the 26 Core Entities and 15 Canonical Relationships', async ({
    page,
  }) => {
    await page.goto('/')
    await page.getByRole('button', { name: /Ontology Explorer/i }).click()

    await expect(page.getByRole('heading', { name: /Software Engineering Ontology Explorer/i })).toBeVisible()
    await expect(page.getByRole('cell', { name: 'Service', exact: true })).toBeVisible()
    await expect(page.getByRole('cell', { name: 'APIEndpoint', exact: true })).toBeVisible()
    await expect(page.getByRole('cell', { name: 'BusinessConcept', exact: true })).toBeVisible()
    await expect(page.getByText('15 Canonical Relationships')).toBeVisible()
    await expect(page.getByText('CALLS').first()).toBeVisible()
    await expect(page.getByText('TRANSFORMS_INTO')).toBeVisible()
  })

  test('Workflow Impact View shows disrupted steps and business exposure', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: /Workflow Impact View/i }).click()

    await expect(page.getByRole('heading', { name: /Business Workflow Impact Reasoning/i })).toBeVisible()
    await expect(page.getByText('Customer Checkout & Payment Flow')).toBeVisible()
    await expect(page.getByText('DISRUPTED BY PR #142').first()).toBeVisible()
    await expect(page.getByText('BREACH').first()).toBeVisible()
  })

  test('Test Recommendations enforces PENDING_HUMAN_REVIEW and supports approving', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: /Test Recommendations/i }).click()

    await expect(page.getByRole('heading', { name: /Automated Remediation & Test Generation/i })).toBeVisible()
    await expect(page.getByText('PENDING_HUMAN_REVIEW').first()).toBeVisible()
    await expect(page.getByText('Compliance Invariant:')).toBeVisible()

    // Approve a test
    const approveBtn = page.getByRole('button', { name: 'Approve for CI' }).first()
    await approveBtn.click()

    await expect(page.getByText('Approved by Analyst').first()).toBeVisible()
  })

  test('Workspace & Team Settings verifies RBAC Permission Matrix', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: /Workspaces & RBAC/i }).click()

    await expect(page.getByRole('heading', { name: 'Workspace & RBAC Access Controls' })).toBeVisible()
    await expect(page.getByRole('cell', { name: 'Core Platform' })).toBeVisible()
    await expect(page.getByText('RBAC Permission Matrix')).toBeVisible()
    await expect(page.getByText('Reveal Plaintext Secrets')).toBeVisible()
  })

  test('Security Audit Logs verifies event stream and payload inspection', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: /Security Audit Logs/i }).click()

    await expect(page.getByRole('heading', { name: 'Security & Compliance Audit Trail' })).toBeVisible()
    await expect(page.getByText('BOLA_ATTEMPT_TRIGGER_SCAN')).toBeVisible()

    // Click on Payload inspection
    await page.getByRole('button', { name: 'Payload' }).first().click()
    await expect(page.getByText('Structured Event Details:')).toBeVisible()
  })
})
