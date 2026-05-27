"""
Bulk source / book library import — CSV, folder scan, staging, duplicate detection.
Read-only folder access; never deletes or moves user files.
"""
import csv
import io
import json
import re
import uuid
from dataclasses import dataclass, field, fields
from difflib import SequenceMatcher
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import Q

from taxonomy.models import Domain, Tag
from taxonomy.utils import get_or_create_uncategorized_domain

from .models import Author, Source

SCAN_EXTENSIONS = {'.pdf', '.docx', '.txt'}
CSV_COLUMNS = [
    'title',
    'subtitle',
    'author',
    'source_type',
    'publisher',
    'publication_year',
    'isbn',
    'edition',
    'primary_domain',
    'priority',
    'status',
    'tags',
    'notes',
    'file_path',
]

SOURCE_TYPE_ALIASES = {
    'book': Source.SourceType.BOOK,
    'standard': Source.SourceType.STANDARD,
    'paper': Source.SourceType.PAPER,
    'contract': Source.SourceType.CONTRACT,
    'report': Source.SourceType.REPORT,
    'lesson_learned': Source.SourceType.LESSON_LEARNED,
    'lesson learned': Source.SourceType.LESSON_LEARNED,
    'article': Source.SourceType.ARTICLE,
    'guide': Source.SourceType.GUIDE,
    'specification': Source.SourceType.SPECIFICATION,
    'manual': Source.SourceType.MANUAL,
    'other': Source.SourceType.OTHER,
}

EXTENSION_SOURCE_TYPE = {
    '.pdf': Source.SourceType.BOOK,
    '.docx': Source.SourceType.MANUAL,
    '.txt': Source.SourceType.MANUAL,
}


@dataclass
class ImportRowPreview:
    row_index: int
    title: str
    subtitle: str = ''
    authors: list = field(default_factory=list)
    source_type: str = Source.SourceType.BOOK
    publisher: str = ''
    year: int | None = None
    isbn: str = ''
    edition: str = ''
    primary_domain_name: str = ''
    domain_resolved: str = ''
    domain_unmatched: bool = False
    priority: str = Source.Priority.MEDIUM
    status: str = Source.Status.NOT_STARTED
    tags: list = field(default_factory=list)
    notes: str = ''
    original_file_path: str = ''
    source_extension: str = ''
    file_size: int | None = None
    duplicate: bool = False
    duplicate_reason: str = ''
    warnings: list = field(default_factory=list)
    selected: bool = True
    skip: bool = False

    def to_dict(self):
        return {
            'row_index': self.row_index,
            'title': self.title,
            'subtitle': self.subtitle,
            'authors': self.authors,
            'source_type': self.source_type,
            'publisher': self.publisher,
            'year': self.year,
            'isbn': self.isbn,
            'edition': self.edition,
            'primary_domain_name': self.primary_domain_name,
            'domain_resolved': self.domain_resolved,
            'domain_unmatched': self.domain_unmatched,
            'priority': self.priority,
            'status': self.status,
            'tags': self.tags,
            'notes': self.notes,
            'original_file_path': self.original_file_path,
            'source_extension': self.source_extension,
            'file_size': self.file_size,
            'duplicate': self.duplicate,
            'duplicate_reason': self.duplicate_reason,
            'warnings': self.warnings,
            'selected': self.selected,
            'skip': self.skip,
        }

    @classmethod
    def from_dict(cls, data: dict):
        known = {f.name for f in fields(cls)}
        return cls(**{k: data[k] for k in known if k in data})


@dataclass
class ImportSummary:
    total_imported: int = 0
    skipped_duplicates: int = 0
    unmatched_domains: int = 0
    failed_rows: int = 0
    scanned_files_count: int = 0
    errors: list = field(default_factory=list)

    def to_dict(self):
        return {
            'total_imported': self.total_imported,
            'skipped_duplicates': self.skipped_duplicates,
            'unmatched_domains': self.unmatched_domains,
            'failed_rows': self.failed_rows,
            'scanned_files_count': self.scanned_files_count,
            'errors': self.errors,
        }


def staging_dir() -> Path:
    path = Path(settings.MEDIA_ROOT) / 'bulk_import_staging'
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_staging(staging_id: str, payload: dict) -> None:
    path = staging_dir() / f'{staging_id}.json'
    with path.open('w', encoding='utf-8') as handle:
        json.dump(payload, handle)


def load_staging(staging_id: str) -> dict | None:
    path = staging_dir() / f'{staging_id}.json'
    if not path.exists():
        return None
    with path.open(encoding='utf-8') as handle:
        return json.load(handle)


def delete_staging(staging_id: str) -> None:
    path = staging_dir() / f'{staging_id}.json'
    if path.exists():
        path.unlink()


def new_staging_id() -> str:
    return str(uuid.uuid4())


def csv_template_content() -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    writer.writerow(
        [
            'NEC4 Engineering and Construction Contract',
            'Core clauses overview',
            'Martin Barnes',
            'book',
            'ICE Publishing',
            '2017',
            '9780727760677',
            '1st',
            'Contracts Management',
            'high',
            'not_started',
            'contracts,nec',
            'Reference for clause extraction',
            '',
        ]
    )
    writer.writerow(
        [
            '# Instructions: publication_year maps to year. author: semicolon-separated. '
            'tags: comma-separated. file_path: optional local path reference only.',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
        ]
    )
    return buffer.getvalue()


def parse_csv_upload(file_obj) -> tuple[list[ImportRowPreview], list[str]]:
    """Parse uploaded CSV into preview rows."""
    errors = []
    try:
        text = file_obj.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        text = file_obj.read().decode('latin-1', errors='replace')

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return [], ['CSV has no header row.']

    normalized_headers = {_normalize_header(h): h for h in reader.fieldnames if h}
    if 'title' not in normalized_headers:
        return [], ['CSV must include a "title" column.']

    rows: list[ImportRowPreview] = []
    for index, raw in enumerate(reader):
        if not any(str(v or '').strip() for v in raw.values()):
            continue
        if str(raw.get(normalized_headers.get('title', 'title'), '')).strip().startswith('#'):
            continue

        row = _csv_row_to_preview(index, raw, normalized_headers)
        _apply_duplicate_checks(row)
        rows.append(row)

    if not rows:
        errors.append('No data rows found in CSV.')
    return rows, errors


def _normalize_header(header: str) -> str:
    return header.strip().lower().replace(' ', '_')


def _csv_row_to_preview(index: int, raw: dict, header_map: dict) -> ImportRowPreview:
    def cell(*keys, default=''):
        for key in keys:
            col = header_map.get(key)
            if col and raw.get(col) is not None:
                return str(raw[col]).strip()
        return default

    title = cell('title')
    author_raw = cell('author')
    authors = _split_authors(author_raw)
    year_raw = cell('publication_year', 'year')
    year = int(year_raw) if year_raw.isdigit() else None

    domain_name = cell('primary_domain', 'domain')
    domain, unmatched = _resolve_domain_name(domain_name)

    row = ImportRowPreview(
        row_index=index,
        title=title,
        subtitle=cell('subtitle'),
        authors=authors,
        source_type=_resolve_source_type(cell('source_type')),
        publisher=cell('publisher'),
        year=year,
        isbn=cell('isbn'),
        edition=cell('edition'),
        primary_domain_name=domain_name,
        domain_resolved=str(domain.pk) if domain else '',
        domain_unmatched=unmatched,
        priority=_resolve_priority(cell('priority')),
        status=_resolve_status(cell('status')),
        tags=_split_tags(cell('tags')),
        notes=cell('notes'),
        original_file_path=cell('file_path', 'original_file_path'),
    )
    if row.original_file_path:
        path = Path(row.original_file_path)
        row.source_extension = path.suffix.lower()
        if path.exists() and path.is_file():
            row.file_size = path.stat().st_size
    return row


def _split_authors(value: str) -> list[str]:
    if not value:
        return []
    parts = re.split(r'[;|]', value)
    return [p.strip() for p in parts if p.strip()]


def _split_tags(value: str) -> list[str]:
    if not value:
        return []
    return [t.strip() for t in value.split(',') if t.strip()]


def _resolve_source_type(value: str) -> str:
    key = value.strip().lower().replace(' ', '_')
    if key in SOURCE_TYPE_ALIASES:
        return SOURCE_TYPE_ALIASES[key]
    if key in dict(Source.SourceType.choices):
        return key
    return Source.SourceType.BOOK


def _resolve_priority(value: str) -> str:
    key = value.strip().lower()
    if key in dict(Source.Priority.choices):
        return key
    return Source.Priority.MEDIUM


def _resolve_status(value: str) -> str:
    key = value.strip().lower().replace(' ', '_')
    if key in dict(Source.Status.choices):
        return key
    return Source.Status.NOT_STARTED


def _resolve_domain_name(name: str) -> tuple[Domain | None, bool]:
    if not name.strip():
        return None, False
    domain = Domain.objects.filter(name__iexact=name.strip()).first()
    if domain:
        return domain, False
    uncategorized = get_or_create_uncategorized_domain()
    return uncategorized, True


def title_from_filename(path: Path) -> str:
    stem = path.stem
    stem = re.sub(r'[_\.\-]+', ' ', stem)
    stem = re.sub(r'\s+', ' ', stem).strip()
    return stem[:500] if stem else path.name


def validate_scan_root(path_str: str) -> Path:
    if not path_str or not path_str.strip():
        raise ValueError('Enter a folder path to scan.')
    root = Path(path_str.strip()).expanduser().resolve()
    if not root.exists():
        raise ValueError(f'Path does not exist: {root}')
    if not root.is_dir():
        raise ValueError(f'Not a directory: {root}')
    return root


def scan_folder(root_path: str, *, max_files: int = 10000) -> tuple[list[ImportRowPreview], list[str]]:
    """Recursively scan folder for PDF/DOCX/TXT (read-only)."""
    errors = []
    try:
        root = validate_scan_root(root_path)
    except ValueError as exc:
        return [], [str(exc)]

    rows: list[ImportRowPreview] = []
    try:
        for path in root.rglob('*'):
            if not path.is_file():
                continue
            ext = path.suffix.lower()
            if ext not in SCAN_EXTENSIONS:
                continue
            try:
                resolved = path.resolve()
                if not resolved.is_relative_to(root):
                    continue
            except (OSError, ValueError):
                continue

            title = title_from_filename(resolved)
            row = ImportRowPreview(
                row_index=len(rows),
                title=title,
                source_type=EXTENSION_SOURCE_TYPE.get(ext, Source.SourceType.OTHER),
                status=Source.Status.NOT_STARTED,
                priority=Source.Priority.MEDIUM,
                original_file_path=str(resolved),
                source_extension=ext,
            )
            try:
                row.file_size = resolved.stat().st_size
            except OSError:
                row.warnings.append('Could not read file size.')

            _apply_duplicate_checks(row, filename=str(resolved))
            rows.append(row)

            if len(rows) >= max_files:
                errors.append(f'Scan stopped at {max_files} files (limit).')
                break
    except PermissionError:
        return [], ['Permission denied accessing folder or subfolders.']
    except OSError as exc:
        return [], [f'Folder scan error: {exc}']

    if not rows:
        errors.append('No PDF, DOCX, or TXT files found.')
    return rows, errors


def _apply_duplicate_checks(row: ImportRowPreview, filename: str = '') -> None:
    title_norm = row.title.strip().lower()
    if not title_norm:
        row.warnings.append('Missing title.')
        return

    qs = Source.objects.filter(title__iexact=row.title.strip())
    if row.authors:
        qs = qs.filter(authors__name__iexact=row.authors[0])
    if qs.exists():
        row.duplicate = True
        row.duplicate_reason = 'Matching title' + (
            f' and author "{row.authors[0]}"' if row.authors else ''
        )
        row.skip = True
        return

    if filename:
        path_norm = str(Path(filename).resolve()).lower()
        existing = Source.objects.filter(original_file_path__iexact=path_norm).first()
        if existing:
            row.duplicate = True
            row.duplicate_reason = f'Path already linked to source "{existing.title}"'
            row.skip = True
            return

    if filename:
        stem = Path(filename).stem.lower()
        for source in Source.objects.filter(original_file_path__isnull=False).exclude(
            original_file_path=''
        )[:2000]:
            other = Path(source.original_file_path).stem.lower()
            if other and SequenceMatcher(None, stem, other).ratio() >= 0.92:
                row.duplicate = True
                row.duplicate_reason = f'Similar filename to existing: {source.title}'
                row.skip = True
                return


def preview_stats(rows: list[ImportRowPreview]) -> dict:
    return {
        'total': len(rows),
        'duplicates': sum(1 for r in rows if r.duplicate),
        'selected': sum(1 for r in rows if r.selected and not r.skip),
        'unmatched_domains': sum(1 for r in rows if r.domain_unmatched),
    }


def rows_from_staging_dict(items: list[dict]) -> list[ImportRowPreview]:
    return [ImportRowPreview.from_dict(item) for item in items]


def rows_to_staging_dict(rows: list[ImportRowPreview]) -> list[dict]:
    return [r.to_dict() for r in rows]


@transaction.atomic
def import_preview_rows(
    rows: list[ImportRowPreview],
    *,
    default_domain_id: str | None = None,
    skip_duplicates: bool = True,
) -> ImportSummary:
    summary = ImportSummary()
    default_domain = None
    if default_domain_id:
        default_domain = Domain.objects.filter(pk=default_domain_id).first()

    author_cache: dict[str, Author] = {}

    for row in rows:
        if not row.selected:
            continue
        if row.skip and skip_duplicates:
            summary.skipped_duplicates += 1
            continue
        if not row.title.strip():
            summary.failed_rows += 1
            summary.errors.append(f'Row {row.row_index + 1}: missing title.')
            continue

        try:
            domain = None
            if row.domain_resolved:
                domain = Domain.objects.filter(pk=row.domain_resolved).first()
            elif default_domain:
                domain = default_domain
            if row.domain_unmatched:
                summary.unmatched_domains += 1

            source = Source.objects.create(
                title=row.title.strip()[:500],
                subtitle=row.subtitle[:500],
                source_type=row.source_type,
                year=row.year,
                edition=row.edition[:100],
                isbn=row.isbn[:20],
                publisher=row.publisher[:255],
                primary_domain=domain,
                priority=row.priority,
                status=row.status,
                notes=row.notes,
                original_file_path=row.original_file_path[:2000],
                source_extension=row.source_extension[:20],
                source_file_size=row.file_size,
            )

            for author_name in row.authors:
                key = author_name.lower()
                if key not in author_cache:
                    author_cache[key], _ = Author.objects.get_or_create(
                        name=author_name[:255],
                        defaults={'organization': ''},
                    )
                source.authors.add(author_cache[key])

            for tag_name in row.tags:
                tag, _ = Tag.objects.get_or_create(name=tag_name[:100])
                source.tags.add(tag)

            summary.total_imported += 1
        except Exception as exc:
            summary.failed_rows += 1
            summary.errors.append(f'Row {row.row_index + 1}: {exc}')

    return summary
