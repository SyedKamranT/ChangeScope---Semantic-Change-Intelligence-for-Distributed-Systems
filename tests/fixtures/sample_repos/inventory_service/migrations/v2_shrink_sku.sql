-- Database Migration: Shrink SKU column and drop legacy audit
ALTER TABLE items ALTER COLUMN sku TYPE VARCHAR(16);
ALTER TABLE items DROP COLUMN legacy_audit_code;
