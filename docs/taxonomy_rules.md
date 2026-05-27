# Taxonomy Rules

## Hierarchy

VIL uses a strict four-level hierarchy plus cross-cutting tags:

```
Domain (required for KnowledgeUnit)
  └── Subdomain (optional)
        └── Topic (optional)
              └── Concept (optional)

Tag (independent, many-to-many with KnowledgeUnit)
```

## Rules

### 1. Domain is mandatory for knowledge units

Every `KnowledgeUnit` must have a `domain`. Subdomain, topic, and concept refine placement but are optional.

### 2. Respect parent chain

When assigning taxonomy to a knowledge unit:

- If `concept` is set → `topic`, `subdomain`, and `domain` should align with that concept’s ancestors.
- If `topic` is set → `subdomain` and `domain` should match the topic’s chain.
- If `subdomain` is set → `domain` should match the subdomain’s domain.

Phase 1 does not enforce this in the database; validate during data entry. Phase 2+ may add model `clean()` validation.

### 3. Uniqueness within parent

- `Subdomain.name` is unique per `Domain`.
- `Topic.name` is unique per `Subdomain`.
- `Concept.name` is unique per `Topic`.
- `Domain.name` and `Tag.name` are globally unique.

### 4. Source primary domain

`Source.primary_domain` is optional but recommended for filtering and dashboard grouping. It does not replace knowledge-unit taxonomy.

### 5. Tags vs hierarchy

Use **hierarchy** for structured navigation and curricula. Use **tags** for flexible cross-cutting themes (e.g. `delay`, `nec4`, `claims`).

### 6. Deletion caution

Deleting a domain cascades to subdomains, topics, and concepts. Knowledge units use `PROTECT` on domain — delete or reassign units first.

### 7. Governance-aware taxonomy review

Phase 5 introduces review governance fields on `KnowledgeUnit`. Taxonomy changes should follow review lifecycle:

- `pending_review` → initial extraction/manual entry stage.
- `reviewed` → taxonomy confirmed by reviewer.
- `approved` → taxonomy validated for production use.
- `archived` → retained but excluded from active use.

Recommended practice:

1. During `pending_review`, set at least `domain`.
2. Before `approved`, ensure subdomain/topic/concept chain is valid.
3. Use `confidence_level` and `source_quality` to prioritize taxonomy cleanup.
4. Use duplicate flags/groups before consolidating near-identical taxonomy placements.

### 8. Duplicate handling and taxonomy

Duplicate marking (`is_duplicate`, `duplicate_group`) does not delete records. Keep one canonical unit with the best taxonomy assignment and archive/merge duplicates after review.

When duplicates have conflicting taxonomy:

- Prefer the unit with stronger source traceability and higher source quality.
- Keep the most specific valid chain (domain → subdomain → topic → concept).
- Document decisions in `approval_notes`.

## Suggested domain examples (construction)

| Domain | Example subdomains |
|--------|-------------------|
| Contracts & Commercial | NEC, FIDIC, variations, claims |
| Project Controls | Planning, cost, risk, reporting |
| Operations & Site | Safety, quality, logistics |
| Standards & Technical | Codes, specifications, materials |

Define your own taxonomy in admin or the Taxonomy UI; the above are examples only.
