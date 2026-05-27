# Naming Conventions

## Python / Django code

| Element | Convention | Example |
|---------|------------|---------|
| Apps | lowercase, single word | `library`, `taxonomy` |
| Models | PascalCase singular | `KnowledgeUnit`, `Source` |
| Fields | snake_case | `review_status`, `executive_insight` |
| Choices | snake_case values, Title Case labels | `in_progress`, `In Progress` |
| URL names | snake_case with namespace | `library:source_list` |
| Templates | lowercase with underscores | `source_list.html` |

## Database

- Table names: Django default (`app_model`).
- Primary keys: UUID (`id`) on all main business models.
- Timestamps: `created_at`, `updated_at` on all `TimestampedModel` records.

## Taxonomy names

- **Domain** — Broad field (e.g. `Project Controls`).
- **Subdomain** — Specialization (e.g. `Schedule Management`).
- **Topic** — Specific subject (e.g. `Critical Path Analysis`).
- **Concept** — Atomic idea (e.g. `Total Float Consumption`).
- Use title case for display names; avoid abbreviations unless industry-standard.

## Sources

- **Title** — Full bibliographic or document title as published.
- **source_type** — Pick the closest enum; use `other` sparingly with notes.
- **chapter_number** — Use publisher numbering (`1`, `1.2`, `Appendix A`).

## Knowledge units

- **title** — Short, searchable headline (under ~120 characters ideal).
- **executive_insight** — One-paragraph “so what” for consultants.
- **keywords** — Comma-separated, lowercase preferred (`delay damages, ld, nec4`).
- **review_status** — Progression: `draft` → `reviewed` → `approved` (or `ai_extracted` in Phase 2).

## Files and media

- Uploaded sources: `media/sources/YYYY/MM/<filename>` (Django default upload path).
- Prompts (Phase 2): `prompts/<workflow>/<version>.md`
- Backups: `backups/YYYY-MM-DD_<description>.sql` or `.json`

## Environment variables

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Django secret |
| `DEBUG` | `True` local only |
| `ALLOWED_HOSTS` | Comma-separated hosts |
| `DATABASE_URL` | PostgreSQL connection string; empty = SQLite |
