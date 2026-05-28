# Architecture — Value Intelligence Library

## Overview

Value Intelligence Library (VIL) is a private, local-first Django web application for capturing, organizing, and retrieving construction management intelligence. Phase 5 adds governance workflow, review queue operations, and bulk quality controls.

## Design principles

1. **Separation** — Standalone from Value Systems SaaS and Moodle.
2. **Clean boundaries** — One Django app per bounded context.
3. **UUID primary keys** — Used for all main business records for stable references across exports and future integrations.
4. **Local-first** — SQLite for frictionless startup; PostgreSQL when `DATABASE_URL` is configured.
5. **Admin + UI parity** — Django admin for bulk data entry; Bootstrap UI for day-to-day browsing and CRUD.

## Application boundaries

| App | Responsibility |
|-----|----------------|
| `config` | Settings, URLs, login middleware, shared abstract models |
| `dashboard` | Home metrics, global keyword search |
| `library` | Authors, Sources (reference materials), Chapters |
| `taxonomy` | Domain → Subdomain → Topic → Concept hierarchy, Tags |
| `knowledge` | Knowledge units, relationships, governance workflow, review queue |
| `ai_extraction` | Prompt templates, extraction batches, candidates, document ingestion |

## Data model relationships

```
Domain
  └── Subdomain
        └── Topic
              └── Concept

Author ──M2M── Source ──1:N── Chapter
                    │
                    └── referenced by KnowledgeUnit

KnowledgeUnit ── FK ── Domain (required)
              ── FK ── Subdomain, Topic, Concept (optional)
              ── FK ── Source, Chapter (optional)
              ── M2M ── Tag
              ── Governance fields: reviewed_by, reviewed_at, governance_status
                                   confidence_level, source_quality, duplicate flags

KnowledgeRelationship: KnowledgeUnit → KnowledgeUnit

DocumentIngestionJob ── FK ── Source
        └── 1:N ── TextChunk ── optional FK ── ExtractionBatch
```

## Document ingestion workflow (Phase 4)

Local PDF/text ingestion — **no external AI APIs**.

```
Source
  └── DocumentIngestionJob (upload PDF or manual text)
        ├── extract_pdf_text()  → extracted_text (pypdf, page markers)
        ├── create_text_chunks() → TextChunk (~12k chars, page ranges)
        └── bulk/single create_batch_from_chunk() → ExtractionBatch
              └── manual Claude → parse JSON
                    ├── Governance path: ExtractionCandidate → review → KnowledgeUnit
                    └── Fast path (Phase 5B): KnowledgeUnit directly (pending review)
```

### Ingestion services (`ai_extraction/ingestion_services.py`)

| Function | Role |
|----------|------|
| `extract_pdf_text(job)` | Page-by-page pypdf extraction; detects scanned/image PDFs |
| `create_text_chunks(job, chunk_size=12000)` | Splits text into chunks with page references |
| `create_batch_from_chunk(chunk, template)` | Links chunk to new `ExtractionBatch` |
| `bulk_create_batches_from_job(job, template)` | Batch creation for unlinked chunks |

### Limitations

- **Scanned PDFs** — pypdf only extracts embedded text; image-only pages fail with a clear error. OCR is a future phase.
- **Chapter detection** — not automated; chunks use page ranges only.
- **Non-PDF files** — use Manual text method and paste content (no pypdf).
- Deleting an ingestion job removes its uploaded file and chunks; existing `ExtractionBatch` records are retained.

## Request flow

1. `LoginRequiredMiddleware` redirects unauthenticated users to `/login/`.
2. Authenticated users access sidebar-linked CRUD and search views.
3. Django admin remains available at `/admin/` for power users.

## Governance workflow (Phase 5)

Review is now explicit and scalable:

1. AI/manual ingestion creates `KnowledgeUnit` records (often `review_status=ai_extracted`).
2. Reviewer works from `/knowledge/review-queue/` (default mode: pending review).
3. Reviewer uses bulk/quick actions:
   - mark reviewed
   - approve
   - archive
   - mark/unmark duplicate
   - update domain/tags/value/confidence
4. On approval:
   - `reviewed_by` = current user
   - `reviewed_at` = timestamp
   - `governance_status` = approved
5. Duplicate handling is rule-based (title similarity, substring, case-insensitive); no embeddings.

## Fast import workflow (Phase 5B)

Optional high-speed ingestion for a solo expert operator. The candidate review stage is **not** removed — it remains the default governance path.

```
ExtractionBatch.ai_output_raw (JSON array)
  ├── Parse to Candidates → ExtractionCandidate (unchanged)
  └── Parse & Fast Import → KnowledgeUnit (skip candidates)
```

### Fast import defaults (`ai_extraction/parsers.py` → `fast_import_batch_ai_output`)

| Field | Value |
|-------|--------|
| `review_status` | `ai_extracted` |
| `governance_status` | `pending_review` |
| `reviewed_by` / `reviewed_at` | null |
| `confidence_level` / `source_quality` | `medium` |
| `would_i_use_this` | `true` |
| `imported_via` | `fast_import` |
| `imported_from_batch` | source batch FK |

Candidate-reviewed imports set `imported_via=candidate_review` and the same governance defaults when imported from a candidate.

### Safety and duplicates

- Invalid JSON at the root: **no** knowledge units created (transaction rolls back parse attempt metadata only for fatal JSON).
- Per-item validation failures are skipped with a summary; valid items still import.
- Exact duplicate titles in the library (`title__iexact`) are skipped.
- Similar titles are flagged in the summary but still imported (review queue + duplicate tools apply).
- Taxonomy names are resolved case-insensitively; subdomain/topic/concept stay null when unmatched (no auto-create).
- **Domain**: matched JSON domain is used; otherwise the `Uncategorized` domain is assigned (created on first use) with a note in `approval_notes`. Fast import never blocks on missing domain.

### Bulk fast import

From a **Document Ingestion** job detail page, **Parse & Fast Import All** runs fast import on every linked batch that has saved `ai_output_raw`.

### When to use which path

| Path | Best for |
|------|----------|
| **Candidates (governance mode)** | Team review, editing before import, rejecting bad extractions |
| **Fast import** | Solo operator, trusted prompts, bulk book/chunk ingestion with post-hoc review in Review Queue |

Fast-imported units appear immediately in search and in `/knowledge/review-queue/` like any other pending item.

## Taxonomy cleanup workflow (Phase 5C)

Dedicated bulk taxonomy editor at `/knowledge/taxonomy-cleanup/` (sidebar: **Knowledge → Taxonomy Cleanup**).

**Default scope** (when no quick mode is selected): knowledge units where domain is `Uncategorized`, or subdomain, topic, or concept is null.

**Quick modes**: Uncategorized, missing subdomain/topic/concept, fast imported, pending review, high consulting value, or all units.

**Bulk panel**: domain, subdomain, topic, concept, add tags, knowledge type, consulting/teaching value, confidence, source quality, governance status. Empty fields mean *do not change* existing values.

**Quick governance actions** on selection: set reviewed, approved, mark duplicate, archive.

**Export**: CSV of the currently filtered result set (`taxonomy-cleanup/export.csv`).

Review Queue is unchanged; use Taxonomy Cleanup for post–fast-import taxonomy fixes and Taxonomy Cleanup + Review Queue for governance.

## Source processing control center (Phase 6)

Operational dashboard at `/library/processing-center/` (sidebar: **Library → Processing Center**).

### Ingestion lifecycle (per source)

```
Source registered
  → DocumentIngestionJob (extract PDF / manual text)
  → TextChunk (~12k chars)
  → ExtractionBatch (manual Claude prompt)
  → Parse JSON → ExtractionCandidate and/or KnowledgeUnit (fast import)
  → Review Queue / Taxonomy Cleanup
  → Approved knowledge
```

### Computed processing status

No DB field — derived in `library/processing.py` from aggregated counts:

`not_started` → `ingestion_pending` → `extraction_pending` → `chunking_pending` → `ai_pending` → `parsing_pending` → `review_pending` → `partially_complete` → `complete` (or `failed` on ingestion/parse failures).

### UI capabilities

- Per-source pipeline row (8 stages with % and color)
- Global metrics, throughput (imported/approved today, approval ratio)
- Quick modes (needs extraction, chunking, AI, parsing, review, etc.)
- Filters + CSV export
- Recent activity feed (ingestion, chunks, parses, imports, approvals)
- Failure list with links to retry extract or re-parse
- Enhanced **Source detail** with metrics, pipeline, activity, quick actions

## Prompt quality & extraction standards (Phase 7)

Structured prompt engineering without external AI APIs.

| Module | Role |
|--------|------|
| `extraction_rules.py` | Reusable instruction blocks composed by style and template flags |
| `quality_profiles.py` | Fast Capture, Balanced, Consultant Grade, Course Creation, Deep Technical |
| `prompt_builder.py` | Dynamic final prompt + JSON schema + source/chunk context |
| `json_schema.py` | Extended JSON spec (backward compatible optional fields) |
| `quality_validation.py` | Non-blocking parse/import warnings |
| `batch_quality.py` | Per-batch governance metrics |

**UI:** Prompt Sandbox (`/ai-extraction/prompt-sandbox/`), batch detail prompt preview with profile selector, extraction guidance cards, extended template form/admin.

See [docs/ai_prompt_standards.md](ai_prompt_standards.md).

## Bulk source / book library import (Phase 8)

Rapid onboarding of large libraries (thousands of files) without manual one-by-one entry. **No OCR**, **no embeddings** — operational ingestion preparation only.

### Entry points

| URL | Purpose |
|-----|---------|
| `/library/bulk-import/` | Import center (CSV upload, folder path, safety notes) |
| `/library/bulk-import/preview/` | Paginated preview, bulk edits, commit |
| `/library/bulk-import/template.csv` | Downloadable CSV template with sample rows |

Sidebar: **Library → Bulk Import**.

### Workflows

**CSV import**

1. Download template → fill columns (`title`, `author`, `primary_domain`, `tags`, optional `file_path`, etc.).
2. Upload → rows staged as JSON under `media/bulk_import_staging/{uuid}.json`.
3. Preview (duplicate flags, domain resolution) → optional bulk domain/priority/status/tags on selected rows.
4. Commit → creates `Source` (+ `Author`, `Tag` as needed). Summary stored in session.

**Folder scanner (read-only)**

1. Enter absolute local path (e.g. `C:\Books\Construction Claims`).
2. Recursive scan for `.pdf`, `.docx`, `.txt` (max 10,000 files per scan).
3. Infers title from filename, `source_type` from extension, `status=not_started`, `priority=medium`.
4. Stores `original_file_path` and `source_file_size` — **never moves or deletes** user files.

### Duplicate handling

Before import, each row is checked for:

- Existing source with same **title** (+ first author if provided)
- Exact **original_file_path** match
- **Filename similarity** (stem ratio ≥ 0.92 vs up to 2,000 existing paths)

Flagged rows show warnings; **Skip flagged duplicates** (default) or import anyway. Commit supports **Import all non-duplicates** (all pages) or **Import checked on this page only**.

Unmatched `primary_domain` values → **Uncategorized** domain (taxonomy helper).

### Source file linking fields

| Field | Role |
|-------|------|
| `original_file_path` | Read-only reference to disk path from scanner/CSV |
| `source_file` | Optional uploaded copy (FileField) |
| `source_file_size` | Bytes from scan or path stat |
| `source_extension` | e.g. `.pdf` |

### Readiness indicators (source list)

Computed in `library/source_readiness.py`: file linked, ingestion started, extraction completed, review completed — shown as compact badges on Source Library (standard/compact view).

### Recommended library organization

- One folder per subject or project; consistent filenames (`Author - Title.pdf`).
- Use CSV for metadata-rich catalogs; folder scan for file-first discovery.
- Assign domains in preview bulk panel or default domain on commit.
- Run Processing Center after import to start ingestion jobs.

### Supported file formats (scanner)

- PDF, DOCX, TXT (read-only discovery; OCR and additional formats are future work).

## Source Review Workspace (Phase 9)

Book-level review hub: one page per source where all extraction output for that book can be triaged, governed, and approved without switching between batches.

**No Claude API**, **no embeddings** — reuses existing batch/candidate/fast-import flows; the workspace is the operational UI layer on top.

### Purpose

Stop reviewing extraction results batch-by-batch. The workspace aggregates:

- `ExtractionCandidate` rows from all `ExtractionBatch` records for the source
- `KnowledgeUnit` rows where `source` matches **or** `imported_from_batch.source` matches

This is the **recommended primary review workflow** after parse/import. Batch detail, candidate list, and Review Queue remain available for narrow or cross-source work.

### Entry points

| URL | Purpose |
|-----|---------|
| `/library/sources/<uuid>/review-workspace/` | Main workspace (tabs, filters, metrics, pipeline) |
| `/library/sources/<uuid>/review-workspace/bulk/` | Bulk actions (candidates + knowledge units) |
| `/library/sources/<uuid>/review-workspace/candidates/<uuid>/action/` | Inline single-candidate import/reject |

**Quick links:** Source detail (**Open Review Workspace**), Processing Center, batch detail, candidate list (`?source=`), knowledge list (`?source=`).

Implementation: `library/review_workspace.py`, `library/review_workspace_views.py`.

### Batch-level processing vs source-level review

| Concern | Batch-level (Phases 2–7) | Source-level (Phase 9) |
|---------|--------------------------|-------------------------|
| **Goal** | Create prompts, run Claude, parse JSON, import one chunk/batch at a time | Review **all** candidates and units for one book in one place |
| **Where** | Batch detail, candidate list, ingestion jobs | Source Review Workspace |
| **Scope** | Single batch / chunk | Entire source (all batches + all imported units) |
| **Metrics** | Parse status, candidate counts per batch | Source pipeline, approval ratio, pending/approved/duplicate counts |
| **When to use** | Extraction and parse operations | Daily governance after import |

Processing Center tracks **operational pipeline** status; the Review Workspace is where **human judgment** happens at book scale.

### Candidate review vs fast-imported knowledge units

| Path | Created how | `imported_via` | Initial state | Workspace tab |
|------|-------------|----------------|---------------|---------------|
| **Candidate review** | Parse JSON → candidates → import selected | `candidate_review` | `pending_review` / `ai_extracted` | **Candidates** (before import), then **Pending Review** |
| **Fast import** | Parse JSON → direct `KnowledgeUnit` creation | `fast_import` | `pending_review` / `ai_extracted` | **Imported Knowledge Units**, **Pending Review** |

Both paths require governance (approve, taxonomy, duplicate handling). The workspace shows provenance via `imported_via` and batch/page filters.

### Workspace tabs

| Tab | Contents |
|-----|----------|
| **Candidates** | All extraction candidates for the source (pending, imported, rejected) |
| **Imported Knowledge Units** | All knowledge units for the source (any governance state) |
| **Pending Review** | Units with `governance_status=pending_review` |
| **Approved** | Units with `governance_status=approved` |
| **Rejected/Archived** | Archived/rejected units (+ rejected candidate count in metrics) |
| **Duplicates** | Units flagged `is_duplicate=True` |

Each tab shows a count badge. Expandable rows reveal full insight / explanation / practical application text.

### Source progress (pipeline header)

Visual stages derived from `library/processing.py`:

**PDF extracted → Chunks → Batches → Parsed → Imported → Reviewed → Approved**

Shown with percentage and state (pending / in progress / complete / failed) at the top of the workspace.

### Review metrics

- Total candidates · Pending candidates · Imported units · Pending review · Approved · Archived/rejected · Duplicate suspects · Approval ratio

### Filters (GET)

Search text, batch, page range, domain, knowledge type, review status, governance status, imported_via, confidence, duplicate flag (knowledge units); import status (candidates).

### Bulk review actions

**Candidates (selected rows):**

- Import selected → creates `KnowledgeUnit` via existing import service
- Reject selected

**Knowledge units (selected rows):**

- Approve · Archive/reject · Set reviewed · Mark duplicate
- Assign domain, subdomain, topic, concept (taxonomy bulk update)
- Add tags · Set confidence · Set consulting value · Set teaching value

Reuses `knowledge.views._apply_bulk_action` and `knowledge.taxonomy_cleanup.apply_taxonomy_cleanup_bulk_update`.

### Inline review actions (single row, no detail page)

**Candidates:** Import · Reject · Edit · Open batch

**Knowledge units:** Approve (✓) · Set reviewed (R) · Archive (A) · Mark duplicate (D) · Confidence dropdown · Edit · Open detail

Posts to workspace candidate action URL or `KnowledgeUnitQuickActionView` with `next_url` returning to the workspace.

### Recommended daily workflow

1. **Bulk import / register sources** — Phase 8 CSV or folder scan; assign domains
2. **Ingest PDF** — Document Ingestion job linked to source; extract text
3. **Create chunks and batches** — chunk large texts; attach prompt templates
4. **Claude workflow** — preview prompt (Sandbox / batch detail), paste JSON output, save
5. **Parse → candidates or fast import** — curate first vs speed first
6. **Review in Source Review Workspace** — book-level tabs, inline + bulk governance
7. **Taxonomy cleanup** — fix Uncategorized, missing subdomain/topic/concept (`/knowledge/taxonomy-cleanup/`)
8. **Approve and curate** — approved units ready for search and future phases

Review Queue and Taxonomy Cleanup remain useful for **cross-source** sweeps; the workspace is optimized for **one book at a time**.

## Phase roadmap

| Phase | Scope |
|-------|--------|
| **1** | Models, admin, CRUD UI, dashboard, filters, keyword search |
| **2** | Manual AI extraction workflow, prompt templates, batches, candidates |
| **3** | Structured JSON parse, bulk candidate import |
| **4** | PDF ingestion, text chunks, automatic batch creation |
| **5** | Review queue, governance fields, bulk operations, duplicate assistance |
| **5B** | Fast import (direct KnowledgeUnit creation), import provenance, bulk fast import from ingestion |
| **5C** | Taxonomy cleanup page — bulk taxonomy, tags, values, governance; filtered export |
| **6** | Source Processing Center — pipeline metrics, status, activity feed, operational dashboard |
| **7** | Prompt quality — extraction rules, profiles, dynamic builder, validation warnings, sandbox |
| **8** | Bulk source import — CSV, folder scanner, staging preview, duplicates, file path linking |
| **9** | Source Review Workspace — book-level candidate + knowledge unit review, tabs, inline/bulk governance |
| **Future** | OCR for scanned PDFs, embeddings, semantic search (not planned in current phases) |

## Configuration

- Environment variables via `.env` (`python-dotenv`).
- `DATABASE_URL` → PostgreSQL via `dj-database-url`.
- Empty `DATABASE_URL` → SQLite at `db.sqlite3`.
- Media uploads: `media/sources/` (library), `media/ingestion/` (ingestion jobs).

## Extension points

- `backups/` — future export/import scripts
- `prompts/` — versioned AI prompt templates (Phase 2)
- `ai_extraction/` — extraction jobs, review queues (Phase 2)
