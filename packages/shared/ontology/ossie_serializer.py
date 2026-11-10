"""Apache Ossie YAML Serializer and Deserializer for ChangeScope Software Engineering Ontology."""

import uuid
from datetime import UTC, datetime
from typing import Any

import yaml

from packages.shared.errors import ParseError


class OssieSerializer:
    """Translates between ChangeScope's CSEO relational models and Apache Ossie YAML specifications."""

    @classmethod
    def to_ossie_yaml(
        cls,
        model_name: str,
        description: str,
        entities: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
        concepts: list[dict[str, Any]] | None = None,
    ) -> str:
        """Serializes ChangeScope entities, relationships, and business concepts into standard Apache Ossie YAML."""
        concept_list = concepts or []

        # 1. Group fields under their respective parent datasets (Service, Endpoint, Table, Event)
        datasets: list[dict[str, Any]] = []

        # Index fields by parent URN if specified in properties
        fields_by_parent: dict[str, list[dict[str, Any]]] = {}
        standalone_entities: list[dict[str, Any]] = []

        for ent in entities:
            etype = ent.get("entity_type")
            if etype in {"APIField", "DatabaseColumn"}:
                parent_urn = ent.get("properties", {}).get("parent_urn") or ent.get("parent_urn")
                if parent_urn:
                    fields_by_parent.setdefault(parent_urn, []).append(ent)
                else:
                    standalone_entities.append(ent)
            else:
                standalone_entities.append(ent)

        for ent in standalone_entities:
            etype = ent.get("entity_type", "Entity")
            urn = ent.get("canonical_urn", f"urn:cseo:unknown:{uuid.uuid4()}")
            name = ent.get("name", urn.split(":")[-1])
            desc = ent.get("description", "")
            props = ent.get("properties", {})

            # Map entity type to Ossie dataset type
            ds_type = "logical"
            if etype == "Service":
                ds_type = "service"
            elif etype == "APIEndpoint":
                ds_type = "interface"
            elif etype in {"DatabaseTable", "Database"}:
                ds_type = "physical_table"
            elif etype in {"EventSchema", "Event"}:
                ds_type = "event_stream"
            elif etype == "Workflow":
                ds_type = "workflow"

            # Build field list for this dataset
            raw_fields = fields_by_parent.get(urn, [])
            ossie_fields: list[dict[str, Any]] = []

            for f in raw_fields:
                fprops = f.get("properties", {})
                ossie_fields.append(
                    {
                        "name": f.get("name", "unnamed_field"),
                        "data_type": fprops.get("data_type", "string"),
                        "description": f.get("description", ""),
                        "ai_context": {
                            "canonical_urn": f.get("canonical_urn"),
                            "entity_type": f.get("entity_type"),
                            "synonyms": fprops.get("synonyms", []),
                            "business_concept": fprops.get("business_concept_urn"),
                            "is_primary_key": fprops.get("is_primary_key", False),
                            "format": fprops.get("format"),
                        },
                    }
                )

            datasets.append(
                {
                    "name": name,
                    "type": ds_type,
                    "description": desc,
                    "fields": ossie_fields,
                    "ai_context": {
                        "canonical_urn": urn,
                        "entity_type": etype,
                        "tier": props.get("tier"),
                        "runtime": props.get("runtime"),
                        "http_method": props.get("http_method"),
                        "path": props.get("path"),
                        "channel": props.get("channel"),
                        "properties": props,
                    },
                }
            )

        # 2. Serialize Relationships
        ossie_relationships: list[dict[str, Any]] = []
        for rel in relationships:
            rel_name = rel.get("id") or f"rel_{rel.get('rel_type', 'DEPENDS')}_{uuid.uuid4().hex[:6]}"
            src = rel.get("source_urn") or rel.get("source_id", "")
            tgt = rel.get("target_urn") or rel.get("target_id", "")
            rtype = rel.get("rel_type", "DEPENDS_ON")

            ossie_relationships.append(
                {
                    "name": rel_name,
                    "type": rtype,
                    "source_dataset": src,
                    "target_dataset": tgt,
                    "join_condition": rel.get("join_condition", f"{src} -> {tgt}"),
                    "ai_context": {
                        "source_type": rel.get("source_type"),
                        "target_type": rel.get("target_type"),
                        "provenance": rel.get("provenance", "STATIC_CONFIRMED"),
                        "confidence": float(rel.get("confidence", 1.0)),
                        "status": rel.get("status", "ACTIVE"),
                        "evidence_refs": rel.get("evidence_refs", []),
                        "source_repo_version": rel.get("source_repo_version"),
                    },
                }
            )

        # 3. Serialize Concepts
        ossie_concepts: list[dict[str, Any]] = []
        for c in concept_list:
            ossie_concepts.append(
                {
                    "urn": c.get("urn", ""),
                    "name": c.get("name", ""),
                    "category": c.get("category", ""),
                    "bounded_context": c.get("bounded_context"),
                    "description": c.get("description", ""),
                    "synonyms": c.get("synonyms", []),
                    "homonym_distinctions": c.get("homonym_distinctions", {}),
                    "constraints": c.get("constraints", {}),
                }
            )

        document: dict[str, Any] = {
            "version": "1.0",
            "standard": "Apache Ossie (incubating)",
            "name": model_name,
            "description": description,
            "generated_at": datetime.now(UTC).isoformat(),
            "concepts": ossie_concepts,
            "datasets": datasets,
            "relationships": ossie_relationships,
        }

        dumped = yaml.dump(document, sort_keys=False, default_flow_style=False)
        return str(dumped) if dumped is not None else ""

    @classmethod
    def from_ossie_yaml(cls, yaml_content: str) -> dict[str, Any]:
        """Parses an Apache Ossie YAML specification into ChangeScope canonical entities and relationships."""
        try:
            doc = yaml.safe_load(yaml_content)
        except yaml.YAMLError as err:
            raise ParseError(f"Malformed Apache Ossie YAML: {err}") from err

        if not isinstance(doc, dict):
            raise ParseError("Invalid Ossie YAML document: root must be a mapping.")

        datasets = doc.get("datasets", [])
        relationships = doc.get("relationships", [])
        concepts = doc.get("concepts", [])

        cseo_entities: list[dict[str, Any]] = []
        cseo_relationships: list[dict[str, Any]] = []
        cseo_concepts: list[dict[str, Any]] = []

        # 1. Parse Datasets and their embedded Fields
        for ds in datasets:
            if not isinstance(ds, dict):
                continue
            ai_ctx = ds.get("ai_context", {})
            etype = ai_ctx.get("entity_type")
            if not etype:
                # Infer from ds.type
                dstype = ds.get("type", "logical")
                if dstype == "service":
                    etype = "Service"
                elif dstype == "interface":
                    etype = "APIEndpoint"
                elif dstype == "physical_table":
                    etype = "DatabaseTable"
                elif dstype == "event_stream":
                    etype = "EventSchema"
                elif dstype == "workflow":
                    etype = "Workflow"
                else:
                    etype = "Service"

            urn = ai_ctx.get("canonical_urn") or f"urn:cseo:{etype.lower()}:{ds.get('name', 'unnamed')}"
            name = ds.get("name", "unnamed")

            cseo_entities.append(
                {
                    "canonical_urn": urn,
                    "entity_type": etype,
                    "name": name,
                    "description": ds.get("description"),
                    "properties": ai_ctx.get("properties", ai_ctx),
                }
            )

            # Unpack fields into child APIField or DatabaseColumn entities
            for f in ds.get("fields", []):
                if not isinstance(f, dict):
                    continue
                fctx = f.get("ai_context", {})
                child_etype = fctx.get("entity_type")
                if not child_etype:
                    child_etype = "DatabaseColumn" if etype == "DatabaseTable" else "APIField"

                fname = f.get("name", "unnamed_field")
                f_urn = fctx.get("canonical_urn") or f"{urn}:field:{fname}"

                child_props = {
                    "data_type": f.get("data_type", "string"),
                    "parent_urn": urn,
                    "synonyms": fctx.get("synonyms", []),
                    "business_concept_urn": fctx.get("business_concept"),
                    "is_primary_key": fctx.get("is_primary_key", False),
                    "format": fctx.get("format"),
                }

                cseo_entities.append(
                    {
                        "canonical_urn": f_urn,
                        "entity_type": child_etype,
                        "name": fname,
                        "description": f.get("description"),
                        "properties": child_props,
                    }
                )

        # 2. Parse Relationships
        for rel in relationships:
            if not isinstance(rel, dict):
                continue
            rctx = rel.get("ai_context", {})
            cseo_relationships.append(
                {
                    "id": rel.get("name", f"rel_{uuid.uuid4().hex[:8]}"),
                    "source_urn": rel.get("source_dataset", ""),
                    "source_type": rctx.get("source_type", "Service"),
                    "target_urn": rel.get("target_dataset", ""),
                    "target_type": rctx.get("target_type", "APIEndpoint"),
                    "rel_type": rel.get("type", "CALLS"),
                    "provenance": rctx.get("provenance", "STATIC_CONFIRMED"),
                    "confidence": float(rctx.get("confidence", 1.0)),
                    "status": rctx.get("status", "ACTIVE"),
                    "evidence_refs": rctx.get("evidence_refs", []),
                    "source_repo_version": rctx.get("source_repo_version"),
                }
            )

        # 3. Parse Business Concepts
        for c in concepts:
            if not isinstance(c, dict):
                continue
            urn = c.get("urn", f"urn:cseo:concept:{uuid.uuid4()}")
            category = c.get("category", "Resource")
            bounded_context = c.get("bounded_context")

            cseo_concepts.append(
                {
                    "urn": urn,
                    "name": c.get("name", urn.split(":")[-1]),
                    "category": category,
                    "bounded_context": bounded_context,
                    "description": c.get("description"),
                    "synonyms": c.get("synonyms", []),
                    "homonym_distinctions": c.get("homonym_distinctions", {}),
                    "constraints": c.get("constraints", {}),
                }
            )

        return {
            "name": doc.get("name", "Imported Ossie Model"),
            "description": doc.get("description", ""),
            "entities": cseo_entities,
            "relationships": cseo_relationships,
            "business_concepts": cseo_concepts,
        }
