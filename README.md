# Value Intelligence Library

Private, local-first Django application for construction management intelligence: books, standards, claims papers, contracts, project controls, operations knowledge, course creation, and consultancy insights.

**Phase 1** includes foundation, database, admin, CRUD screens, dashboard, and search/filter. No AI, embeddings, or RAG in this phase.

This project is **completely separate** from Value Systems SaaS and Moodle.

---

## Requirements

- Python 3.11+ (3.12 recommended)
- Optional: PostgreSQL for production-like local use
- SQLite is used automatically when `DATABASE_URL` is not set

---

## Quick start

### 1. Create and activate virtual environment

**Windows (PowerShell):**

```powershell
cd "C:\Users\haytham.samir\Desktop\Value Intelligence Library"
py -3 -m venv venv
.\venv\Scripts\Activate.ps1
```

> If `python` is on your PATH, you can use `python -m venv venv` instead of `py -3`.

**Windows (Command Prompt):**

```cmd
cd "C:\Users\haytham.samir\Desktop\Value Intelligence Library"
python -m venv venv
venv\Scripts\activate.bat
```

**macOS / Linux:**

```bash
cd /path/to/Value Intelligence Library
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

(With venv activated, or use `.\venv\Scripts\python.exe -m pip install -r requirements.txt` on Windows without activating.)

### 3. Environment configuration

```bash
copy .env.example .env
```

Edit `.env` and set at minimum a strong `SECRET_KEY`. Example:

```
SECRET_KEY=your-long-random-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=
```

Leave `DATABASE_URL` empty to use SQLite (`db.sqlite3` in the project root).

For PostgreSQL:

```
DATABASE_URL=postgres://user:password@localhost:5432/value_intelligence_library
```

### 4. Database migrations

```bash
python manage.py migrate
```

### 5. Create superuser (admin access only)

```bash
python manage.py createsuperuser
```

There is no public registration. Only superusers/staff can sign in.

### 7. Seed default taxonomy (optional)

```bash
python manage.py seed_taxonomy
```

Creates 12 construction-management domains with starter subdomains (skips duplicates if run again).

### 8. Seed AI prompt templates (optional, after taxonomy)

```bash
python manage.py seed_prompt_templates
```

Creates six starter extraction prompt templates for the manual Claude workflow at `/ai-extraction/`.

Refresh templates with JSON instructions:

```bash
python manage.py seed_prompt_templates --update
```

### 9. Document ingestion (Phase 4)

Upload PDFs under **AI Extraction → Document Ingestion** (or from a Source detail page):

1. Create ingestion job (link to Source, upload PDF)
2. **Extract text from PDF** (pypdf)
3. **Create text chunks** (~12,000 characters, with page ranges when available)
4. **Create extraction batches** (per chunk or bulk with one prompt template)
5. Continue in Extraction Batches → copy prompt to Claude → save JSON output, then either:
   - **Parse to Candidates** — review each candidate, then import (governance mode), or
   - **Parse & Fast Import** — create knowledge units directly as pending review items (solo operator mode)

From an ingestion job with multiple batches that already have AI output saved, use **Parse & Fast Import All** for bulk fast import.

**Scanned/image-only PDFs** are not supported yet — use Manual text and paste content, or wait for a future OCR phase.

### Fast import vs candidate review (Phase 5B)

| Mode | Use when |
|------|----------|
| **Parse to Candidates** | You want to edit, reject, or curate extractions before they enter the knowledge base |
| **Parse & Fast Import** | You are a solo expert ingesting at speed; review later in **Source Review Workspace** or **Review Queue** |

Fast import does **not** bypass governance: units are `pending_review`, searchable immediately, and visible in duplicate review tools. Exact duplicate titles in the library are skipped automatically. If the JSON domain is missing or does not match taxonomy, units are assigned to the **Uncategorized** domain (created on first use).

### Taxonomy cleanup (Phase 5C)

After fast import, open **Knowledge → Taxonomy Cleanup** (`/knowledge/taxonomy-cleanup/`) to bulk-assign domain, subdomain, topic, concept, tags, and review values. The default view shows units needing taxonomy work (Uncategorized or missing subdomain/topic/concept). Empty bulk fields leave existing values unchanged. Export the filtered list as CSV. Use **Review Queue** for per-item governance actions.

### Processing Center (Phase 6)

Open **Library → Processing Center** (`/library/processing-center/`) to track every source through the pipeline: ingestion → chunks → batches → parse → import → review → approval. Each source shows counts, a visual pipeline, and computed processing status. Use quick modes (e.g. **Needs Parsing**, **Needs Review**) and CSV export for operational triage. Source detail pages include the same metrics plus recent activity and failure retry links.

### Prompt quality (Phase 7)

Configure **Prompt Templates** with extraction style, granularity, quality threshold, and required-field flags. Use **AI Extraction → Prompt Sandbox** to preview the full generated prompt (rules + JSON schema + source context) before pasting into Claude. On batch detail, use **Preview final prompt** and optional **quality profiles** (Fast Capture through Deep Technical Analysis). Parse/import adds non-blocking quality warnings — see [docs/ai_prompt_standards.md](docs/ai_prompt_standards.md).

### Bulk source import (Phase 8)

Onboard large book/document libraries via **Library → Bulk Import** (`/library/bulk-import/`):

1. **CSV** — download the template, fill metadata columns (`title`, `author`, `primary_domain`, `tags`, optional `file_path`), upload, preview, then import.
2. **Folder scanner** — enter a local root path (e.g. `C:\Books\Claims`); the app recursively discovers PDF, DOCX, and TXT files (**read-only** — originals are never moved or deleted).

Preview shows duplicate warnings (title + author, path, filename similarity). Use **Import all non-duplicates** for full-library commits across paginated preview. Unmatched domains map to **Uncategorized**. Sources store `original_file_path`, extension, and file size for later ingestion. See [docs/architecture.md](docs/architecture.md#bulk-source--book-library-import-phase-8).

### Source Review Workspace (Phase 9)

The **Source Review Workspace** (`/library/sources/<id>/review-workspace/`) is the main place to review a whole book/source in one session — without jumping batch-by-batch.

Open from **Source detail → Open Review Workspace**, or from Processing Center, batch detail, candidate list, or knowledge list (when filtered by source).

**What it shows for one source:**

- All **ExtractionCandidates** from batches linked to that source
- All **KnowledgeUnits** linked directly to the source or imported from its batches

**Tabs:** Candidates · Imported Knowledge Units · Pending Review · Approved · Rejected/Archived · Duplicates

**Actions:** Inline approve/review/archive/duplicate/import/reject; bulk approve, taxonomy assignment, tags, confidence/consulting/teaching values. Expandable rows show executive insight, detailed explanation, and practical application without opening each record.

**Candidate review vs fast import:** Candidates are curated before entering the knowledge base (`imported_via=candidate_review`). Fast-imported units skip the candidate step and land as `pending_review` (`imported_via=fast_import`) — both appear in the workspace for governance.

**Recommended daily workflow:**

1. Bulk import / register sources (Phase 8)
2. Ingest PDF (Document Ingestion)
3. Create chunks and extraction batches
4. Run the manual Claude workflow (copy prompt → paste JSON)
5. Parse to **candidates** or **fast import**
6. **Review in Source Review Workspace** (book-level)
7. Taxonomy cleanup for Uncategorized or missing fields
8. Approve and curate approved knowledge

See [docs/architecture.md](docs/architecture.md#source-review-workspace-phase-9) for batch vs source-level review and full action reference.

### 6. Run development server

```bash
python manage.py runserver
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) and sign in. Django admin: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

---

## Project structure

```
config/           # Django settings, URLs, middleware, shared base models
dashboard/        # Home dashboard and keyword search
library/          # Authors, Sources, Chapters
taxonomy/         # Domain, Subdomain, Topic, Concept, Tag
knowledge/        # KnowledgeUnit, KnowledgeRelationship
ai_extraction/    # Prompts, batches, candidates, ingestion, fast import
templates/        # Bootstrap UI templates
static/           # CSS and static assets
media/            # Uploaded source files
backups/          # Reserved for future backup exports
prompts/          # Reserved for Phase 2 AI prompts
docs/             # Architecture and standards documentation
```

---

## Documentation

- [docs/architecture.md](docs/architecture.md)
- [docs/taxonomy_rules.md](docs/taxonomy_rules.md)
- [docs/naming_conventions.md](docs/naming_conventions.md)
- [docs/ai_prompt_standards.md](docs/ai_prompt_standards.md)

---

## Security notes

- All app pages require login (middleware-enforced).
- No public user registration.
- Local development only; do not expose `DEBUG=True` to the internet.
- Change `SECRET_KEY` before any non-local use.
