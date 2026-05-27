# AI Prompt Standards — Value Intelligence Library

Phase 7 adds **structured prompt engineering**, **quality profiles**, **centralized extraction rules**, and **non-blocking quality validation**. Still no in-app AI API, embeddings, RAG, or chat.

## Extraction philosophy

1. **Atomic knowledge units** — one reusable professional idea per JSON object.
2. **Traceability** — quotes, page/section references, and citations when the source supports them.
3. **Actionable intelligence** — consulting, operational, and course implications where relevant.
4. **Governance by design** — extraction quality rules shape prompts; validation warns on parse/import without blocking.
5. **Fast capture vs curated intelligence** — use quality profiles to trade speed for depth.

## Atomic knowledge unit

A single principle, process, risk, formula, checklist item, decision rule, or lesson learned that stands alone for search, review, and reuse.

**Not atomic:** chapter summaries, motivational statements, duplicate restatements of the same idea.

## Prompt template fields (Phase 7)

| Field | Purpose |
|-------|---------|
| `extraction_style` | consultant, contract_analysis, course_creation, etc. — selects rule packs |
| `target_granularity` | high_level, medium, atomic |
| `minimum_quality_threshold` | low, medium, high — validation strictness |
| `require_*` booleans | Enforce fields in JSON schema and validation warnings |
| `avoid_generic_filler` | Inject filler-avoidance rules (default true) |

## Quality profiles

Applied at preview/sandbox time (optional overlay on template settings):

| Profile | Use when |
|---------|----------|
| **Fast Capture** | Speed-first ingestion; thinner bar, fewer required fields |
| **Balanced** | Default professional extraction with traceability |
| **Consultant Grade** | Advisory-ready depth, atomic units, implications |
| **Course Creation** | Teaching use cases emphasized |
| **Deep Technical Analysis** | Contracts, claims, controls — high bar |

Configure on batch detail via **Quality profile** dropdown, or in **Prompt Sandbox**.

## Dynamic prompt builder

`ai_extraction/prompt_builder.py` assembles:

1. Extraction behavior (style, granularity, threshold, profile)
2. Source context (type, domain, title, authors, chapter, chunk pages)
3. Core template `prompt_text`
4. Centralized rules from `extraction_rules.py`
5. Template `output_format_notes`
6. JSON schema from `json_schema.py`
7. Source text

`ExtractionBatch.build_combined_prompt()` delegates to this builder (backward compatible).

## JSON schema (extended, backward compatible)

Core keys unchanged. Optional extended keys (ignored by older parsers if absent):

- `page_reference`, `source_traceability_note`
- `operational_implication`, `contractual_implication`, `financial_implication`, `schedule_implication`
- `field_application`, `risk_if_ignored`

Extended fields are merged into `detailed_explanation` / `citation` / `reviewer_notes` on import. `page_reference` maps to `KnowledgeUnit.page_reference` on fast import and candidate import (via notes).

## Quality validation (warnings only)

`ai_extraction/quality_validation.py` flags:

- Short or generic titles
- Thin insights, filler phrases
- Missing required fields per template
- Missing traceability / page references
- Excessive length

Warnings are stored in `reviewer_notes` and counted in parse summaries. **Import is never blocked.**

## Manual workflow (unchanged steps)

1. Create batch → preview final prompt (batch detail or sandbox)
2. Copy to Claude manually
3. Save `ai_output_raw`
4. Parse to candidates **or** fast import
5. Review queue / taxonomy cleanup / approve

## Governance modes

| Mode | Path | Governance |
|------|------|------------|
| **Curated (candidates)** | Parse → review candidates → import | Highest control |
| **Fast capture** | Parse & fast import | Speed; fix taxonomy/review after |

## Batch quality metrics

Batch detail shows: candidate/import counts, approval and duplicate ratios, rejection ratio, typical confidence.

## Out of scope

- Claude API integration
- Embeddings / vector DB / in-app chat
- Automatic relationship inference

## Versioning

- Deactivate outdated templates (`is_active = false`) instead of deleting.
- Use Prompt Sandbox to validate prompt changes before production batches.
