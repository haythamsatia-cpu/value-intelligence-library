"""
Source processing pipeline metrics, status computation, filters, and activity feed.
No DB fields — computed from existing ingestion / batch / knowledge models.
"""
from dataclasses import dataclass, field
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from ai_extraction.models import DocumentIngestionJob, ExtractionBatch, ExtractionCandidate, TextChunk
from knowledge.models import KnowledgeUnit

from .models import Source

PROCESSING_STATUS_CHOICES = [
    ('not_started', 'Not Started'),
    ('ingestion_pending', 'Ingestion Pending'),
    ('extraction_pending', 'Extraction Pending'),
    ('chunking_pending', 'Chunking Pending'),
    ('ai_pending', 'AI Pending'),
    ('parsing_pending', 'Parsing Pending'),
    ('review_pending', 'Review Pending'),
    ('partially_complete', 'Partially Complete'),
    ('complete', 'Complete'),
    ('failed', 'Failed'),
]

QUICK_MODES = [
    ('', 'All sources'),
    ('needs_extraction', 'Needs Extraction'),
    ('needs_chunking', 'Needs Chunking'),
    ('needs_ai', 'Needs AI'),
    ('needs_parsing', 'Needs Parsing'),
    ('needs_review', 'Needs Review'),
    ('fully_approved', 'Fully Approved'),
    ('has_failures', 'Has Failures'),
    ('recently_active', 'Recently Active'),
]

PIPELINE_LABELS = [
    ('registered', 'Registered'),
    ('extracted', 'Extracted'),
    ('chunked', 'Chunked'),
    ('batches', 'Batches Created'),
    ('parsed', 'Parsed'),
    ('imported', 'Imported'),
    ('reviewed', 'Reviewed'),
    ('approved', 'Approved'),
]


@dataclass
class SourceProcessingStats:
    source_id: str
    ingestion_jobs_count: int = 0
    ingestion_extracted_count: int = 0
    ingestion_failed_count: int = 0
    text_chunks_count: int = 0
    chunks_with_batch_count: int = 0
    extraction_batches_count: int = 0
    batches_with_ai_output_count: int = 0
    parsed_batches_count: int = 0
    failed_batches_count: int = 0
    candidate_count: int = 0
    imported_knowledge_units_count: int = 0
    approved_knowledge_units_count: int = 0
    pending_review_units_count: int = 0
    duplicate_suspects_count: int = 0
    reviewed_knowledge_units_count: int = 0
    processing_status: str = 'not_started'
    processing_status_label: str = 'Not Started'
    pipeline: list = field(default_factory=list)

    def to_dict(self):
        return {
            'ingestion_jobs_count': self.ingestion_jobs_count,
            'ingestion_extracted_count': self.ingestion_extracted_count,
            'ingestion_failed_count': self.ingestion_failed_count,
            'text_chunks_count': self.text_chunks_count,
            'chunks_with_batch_count': self.chunks_with_batch_count,
            'extraction_batches_count': self.extraction_batches_count,
            'batches_with_ai_output_count': self.batches_with_ai_output_count,
            'parsed_batches_count': self.parsed_batches_count,
            'failed_batches_count': self.failed_batches_count,
            'candidate_count': self.candidate_count,
            'imported_knowledge_units_count': self.imported_knowledge_units_count,
            'approved_knowledge_units_count': self.approved_knowledge_units_count,
            'pending_review_units_count': self.pending_review_units_count,
            'duplicate_suspects_count': self.duplicate_suspects_count,
            'reviewed_knowledge_units_count': self.reviewed_knowledge_units_count,
            'processing_status': self.processing_status,
            'processing_status_label': self.processing_status_label,
            'pipeline': self.pipeline,
        }


def _pct(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 100 if numerator > 0 else 0
    return min(100, int(numerator * 100 / denominator))


def _stage_state(pct: int, failed: bool = False) -> str:
    if failed:
        return 'failed'
    if pct >= 100:
        return 'complete'
    if pct > 0:
        return 'in_progress'
    return 'pending'


def _build_pipeline(stats: SourceProcessingStats) -> list[dict]:
    ing = stats.ingestion_jobs_count
    ext = stats.ingestion_extracted_count
    chunks = stats.text_chunks_count
    batches = stats.extraction_batches_count
    with_batch = stats.chunks_with_batch_count
    ai_out = stats.batches_with_ai_output_count
    parsed = stats.parsed_batches_count
    imported = stats.imported_knowledge_units_count
    reviewed = stats.reviewed_knowledge_units_count
    approved = stats.approved_knowledge_units_count
    ku_total = max(imported, 1)

    ing_failed = stats.ingestion_failed_count > 0
    batch_failed = stats.failed_batches_count > 0

    return [
        {'key': 'registered', 'label': 'Registered', 'pct': 100, 'state': 'complete'},
        {
            'key': 'extracted',
            'label': 'Extracted',
            'pct': _pct(ext, ing) if ing else (100 if ext else 0),
            'state': _stage_state(_pct(ext, ing) if ing else (100 if ext else 0), ing_failed and ext == 0),
        },
        {
            'key': 'chunked',
            'label': 'Chunked',
            'pct': 100 if chunks else 0,
            'state': _stage_state(100 if chunks else 0),
        },
        {
            'key': 'batches',
            'label': 'Batches Created',
            'pct': _pct(with_batch, chunks) if chunks else (100 if batches else 0),
            'state': _stage_state(_pct(with_batch, chunks) if chunks else (100 if batches else 0)),
        },
        {
            'key': 'parsed',
            'label': 'Parsed',
            'pct': _pct(parsed, ai_out) if ai_out else (100 if parsed else 0),
            'state': _stage_state(_pct(parsed, ai_out) if ai_out else (100 if parsed else 0), batch_failed),
        },
        {
            'key': 'imported',
            'label': 'Imported',
            'pct': _pct(imported, ku_total) if imported else 0,
            'state': _stage_state(_pct(imported, ku_total) if imported else 0),
        },
        {
            'key': 'reviewed',
            'label': 'Reviewed',
            'pct': _pct(reviewed, ku_total) if imported else 0,
            'state': _stage_state(_pct(reviewed, ku_total) if imported else 0),
        },
        {
            'key': 'approved',
            'label': 'Approved',
            'pct': _pct(approved, ku_total) if imported else 0,
            'state': _stage_state(_pct(approved, ku_total) if imported else 0),
        },
    ]


def compute_processing_status(stats: SourceProcessingStats) -> tuple[str, str]:
    if stats.ingestion_failed_count > 0 and stats.ingestion_extracted_count == 0:
        return 'failed', 'Failed'
    if stats.failed_batches_count > 0 and stats.parsed_batches_count == 0 and stats.batches_with_ai_output_count > 0:
        return 'failed', 'Failed'

    has_ku = stats.imported_knowledge_units_count > 0
    if has_ku and stats.pending_review_units_count == 0 and stats.approved_knowledge_units_count > 0:
        if stats.approved_knowledge_units_count >= stats.imported_knowledge_units_count:
            return 'complete', 'Complete'
        return 'partially_complete', 'Partially Complete'

    if stats.pending_review_units_count > 0:
        return 'review_pending', 'Review Pending'

    if has_ku:
        return 'partially_complete', 'Partially Complete'

    if stats.batches_with_ai_output_count > stats.parsed_batches_count:
        return 'parsing_pending', 'Parsing Pending'

    if stats.extraction_batches_count > 0 and stats.batches_with_ai_output_count == 0:
        return 'ai_pending', 'AI Pending'

    if stats.text_chunks_count > 0 and stats.extraction_batches_count == 0:
        return 'ai_pending', 'AI Pending'

    if stats.ingestion_extracted_count > 0 and stats.text_chunks_count == 0:
        return 'chunking_pending', 'Chunking Pending'

    if stats.ingestion_jobs_count > 0 and stats.ingestion_extracted_count == 0:
        return 'extraction_pending', 'Extraction Pending'

    if stats.ingestion_jobs_count == 0:
        return 'ingestion_pending', 'Ingestion Pending'

    return 'not_started', 'Not Started'


def bulk_source_processing_stats(source_ids: list) -> dict[str, SourceProcessingStats]:
    if not source_ids:
        return {}

    result = {str(sid): SourceProcessingStats(source_id=str(sid)) for sid in source_ids}

    for row in (
        DocumentIngestionJob.objects.filter(source_id__in=source_ids)
        .values('source_id')
        .annotate(
            total=Count('id'),
            extracted=Count('id', filter=Q(status=DocumentIngestionJob.Status.EXTRACTED)),
            failed=Count('id', filter=Q(status=DocumentIngestionJob.Status.FAILED)),
        )
    ):
        s = result[str(row['source_id'])]
        s.ingestion_jobs_count = row['total']
        s.ingestion_extracted_count = row['extracted']
        s.ingestion_failed_count = row['failed']

    for row in (
        TextChunk.objects.filter(source_id__in=source_ids)
        .values('source_id')
        .annotate(
            total=Count('id'),
            with_batch=Count('id', filter=Q(created_batch__isnull=False)),
        )
    ):
        s = result[str(row['source_id'])]
        s.text_chunks_count = row['total']
        s.chunks_with_batch_count = row['with_batch']

    batch_filter = Q(source_id__in=source_ids)
    for row in (
        ExtractionBatch.objects.filter(batch_filter)
        .values('source_id')
        .annotate(
            total=Count('id'),
            with_ai=Count('id', filter=~Q(ai_output_raw='')),
            parsed=Count('id', filter=Q(parsed_at__isnull=False)),
            failed=Count('id', filter=~Q(parse_error='')),
        )
    ):
        sid = row['source_id']
        if sid is None:
            continue
        s = result[str(sid)]
        s.extraction_batches_count = row['total']
        s.batches_with_ai_output_count = row['with_ai']
        s.parsed_batches_count = row['parsed']
        s.failed_batches_count = row['failed']

    for row in (
        ExtractionCandidate.objects.filter(batch__source_id__in=source_ids)
        .values('batch__source_id')
        .annotate(total=Count('id'))
    ):
        sid = row['batch__source_id']
        if sid:
            result[str(sid)].candidate_count = row['total']

    for row in (
        KnowledgeUnit.objects.filter(source_id__in=source_ids)
        .values('source_id')
        .annotate(
            total=Count('id'),
            approved=Count('id', filter=Q(governance_status=KnowledgeUnit.GovernanceStatus.APPROVED)),
            pending=Count('id', filter=Q(governance_status=KnowledgeUnit.GovernanceStatus.PENDING_REVIEW)),
            duplicates=Count('id', filter=Q(is_duplicate=True)),
            reviewed=Count(
                'id',
                filter=Q(
                    governance_status__in=[
                        KnowledgeUnit.GovernanceStatus.REVIEWED,
                        KnowledgeUnit.GovernanceStatus.APPROVED,
                    ]
                ),
            ),
        )
    ):
        s = result[str(row['source_id'])]
        s.imported_knowledge_units_count = row['total']
        s.approved_knowledge_units_count = row['approved']
        s.pending_review_units_count = row['pending']
        s.duplicate_suspects_count = row['duplicates']
        s.reviewed_knowledge_units_count = row['reviewed']

    for s in result.values():
        status, label = compute_processing_status(s)
        s.processing_status = status
        s.processing_status_label = label
        s.pipeline = _build_pipeline(s)

    return result


def matches_quick_mode(stats: SourceProcessingStats, mode: str) -> bool:
    if not mode:
        return True
    if mode == 'needs_extraction':
        return stats.ingestion_jobs_count > 0 and stats.ingestion_extracted_count < stats.ingestion_jobs_count
    if mode == 'needs_chunking':
        return stats.ingestion_extracted_count > 0 and stats.text_chunks_count == 0
    if mode == 'needs_ai':
        return stats.text_chunks_count > 0 and (
            stats.extraction_batches_count == 0
            or stats.batches_with_ai_output_count < stats.extraction_batches_count
        )
    if mode == 'needs_parsing':
        return stats.batches_with_ai_output_count > stats.parsed_batches_count
    if mode == 'needs_review':
        return stats.pending_review_units_count > 0
    if mode == 'fully_approved':
        return (
            stats.imported_knowledge_units_count > 0
            and stats.pending_review_units_count == 0
            and stats.approved_knowledge_units_count >= stats.imported_knowledge_units_count
        )
    if mode == 'has_failures':
        return stats.ingestion_failed_count > 0 or stats.failed_batches_count > 0
    if mode == 'recently_active':
        return stats.processing_status not in ('not_started', 'ingestion_pending')
    return True


def apply_processing_center_filters(request, qs):
    source_type = request.GET.get('source_type')
    if source_type in dict(Source.SourceType.choices):
        qs = qs.filter(source_type=source_type)
    primary_domain = request.GET.get('primary_domain')
    if primary_domain:
        qs = qs.filter(primary_domain_id=primary_domain)
    priority = request.GET.get('priority')
    if priority in dict(Source.Priority.choices):
        qs = qs.filter(priority=priority)
    status = request.GET.get('status')
    if status in dict(Source.Status.choices):
        qs = qs.filter(status=status)
    created_from = parse_date(request.GET.get('created_from', '') or '')
    if created_from:
        qs = qs.filter(created_at__date__gte=created_from)
    created_to = parse_date(request.GET.get('created_to', '') or '')
    if created_to:
        qs = qs.filter(created_at__date__lte=created_to)
    updated_from = parse_date(request.GET.get('updated_from', '') or '')
    if updated_from:
        qs = qs.filter(updated_at__date__gte=updated_from)
    updated_to = parse_date(request.GET.get('updated_to', '') or '')
    if updated_to:
        qs = qs.filter(updated_at__date__lte=updated_to)
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(notes__icontains=q)
            | Q(isbn__icontains=q)
            | Q(publisher__icontains=q)
        )
    ordering = request.GET.get('ordering', '-updated_at')
    ordering_map = {
        '-updated_at': '-updated_at',
        'updated_at': 'updated_at',
        '-created_at': '-created_at',
        'title': 'title',
    }
    return qs.order_by(ordering_map.get(ordering, '-updated_at'))


def filter_sources_by_processing(request, qs):
    """Apply processing_status and quick mode filters (requires stats)."""
    mode = request.GET.get('mode', '')
    status_filter = request.GET.get('processing_status', '')
    source_ids = list(qs.values_list('pk', flat=True))
    if not source_ids:
        return qs.none(), {}
    stats_map = bulk_source_processing_stats(source_ids)
    filtered_ids = []
    for sid in source_ids:
        stats = stats_map.get(str(sid))
        if not stats:
            continue
        if status_filter and stats.processing_status != status_filter:
            continue
        if not matches_quick_mode(stats, mode):
            continue
        filtered_ids.append(sid)
    return qs.filter(pk__in=filtered_ids), stats_map


def get_global_processing_metrics():
    today = timezone.now().date()
    sources = Source.objects.count()
    active_sources = Source.objects.filter(status=Source.Status.IN_PROGRESS).count()

    chunks = TextChunk.objects.count()
    batches = ExtractionBatch.objects.count()
    parsed_batches = ExtractionBatch.objects.filter(parsed_at__isnull=False).count()
    failed_parses = ExtractionBatch.objects.exclude(parse_error='').count()
    failed_ingestion = DocumentIngestionJob.objects.filter(status=DocumentIngestionJob.Status.FAILED).count()

    ku = KnowledgeUnit.objects.all()
    total_imported = ku.count()
    approved_units = ku.filter(governance_status=KnowledgeUnit.GovernanceStatus.APPROVED).count()
    pending_review = ku.filter(governance_status=KnowledgeUnit.GovernanceStatus.PENDING_REVIEW).count()
    duplicate_suspects = ku.filter(is_duplicate=True).count()

    imported_today = ku.filter(created_at__date=today).count()
    approved_today = ku.filter(
        governance_status=KnowledgeUnit.GovernanceStatus.APPROVED,
        reviewed_at__date=today,
    ).count()

    approval_ratio = 0
    if total_imported:
        approval_ratio = int(approved_units * 100 / total_imported)

    source_ids = list(Source.objects.values_list('pk', flat=True))
    stats_map = bulk_source_processing_stats(source_ids)
    sources_pending_review = sum(1 for s in stats_map.values() if s.pending_review_units_count > 0)
    sources_fully_approved = sum(
        1
        for s in stats_map.values()
        if s.imported_knowledge_units_count > 0
        and s.pending_review_units_count == 0
        and s.approved_knowledge_units_count >= s.imported_knowledge_units_count
    )

    return {
        'total_sources': sources,
        'active_sources': active_sources,
        'sources_pending_review': sources_pending_review,
        'sources_fully_approved': sources_fully_approved,
        'total_chunks': chunks,
        'total_batches': batches,
        'parsed_batches': parsed_batches,
        'failed_parses': failed_parses,
        'failed_ingestion': failed_ingestion,
        'total_imported_units': total_imported,
        'approved_units': approved_units,
        'duplicate_suspects': duplicate_suspects,
        'pending_review_units': pending_review,
        'imported_today': imported_today,
        'approved_today': approved_today,
        'approval_ratio': approval_ratio,
    }


def get_recent_activity(limit: int = 25, source_id=None) -> list[dict]:
    events = []
    job_qs = DocumentIngestionJob.objects.select_related('source').order_by('-updated_at')
    if source_id:
        job_qs = job_qs.filter(source_id=source_id)
    for job in job_qs[:15]:
        if job.status == DocumentIngestionJob.Status.EXTRACTED:
            events.append(
                {
                    'at': job.updated_at,
                    'message': f'PDF/text extracted for "{job.source.title}"',
                    'url_name': 'ai_extraction:ingestion_detail',
                    'url_kwargs': {'pk': job.pk},
                }
            )
        elif job.status == DocumentIngestionJob.Status.FAILED:
            events.append(
                {
                    'at': job.updated_at,
                    'message': f'Extraction failed for "{job.source.title}"',
                    'url_name': 'ai_extraction:ingestion_detail',
                    'url_kwargs': {'pk': job.pk},
                }
            )

    chunk_qs = TextChunk.objects.select_related('source', 'ingestion_job').order_by('-created_at')
    if source_id:
        chunk_qs = chunk_qs.filter(source_id=source_id)
    for chunk in chunk_qs[:10]:
        events.append(
            {
                'at': chunk.created_at,
                'message': f'Chunks created: "{chunk.title}" ({chunk.source.title})',
                'url_name': 'ai_extraction:chunk_detail',
                'url_kwargs': {'pk': chunk.pk},
            }
        )

    batch_qs = ExtractionBatch.objects.select_related('source').filter(parsed_at__isnull=False).order_by(
        '-parsed_at'
    )
    if source_id:
        batch_qs = batch_qs.filter(source_id=source_id)
    for batch in batch_qs[:10]:
        events.append(
            {
                'at': batch.parsed_at,
                'message': f'Batch parsed: "{batch.title}"',
                'url_name': 'ai_extraction:batch_detail',
                'url_kwargs': {'pk': batch.pk},
            }
        )

    ku_qs = KnowledgeUnit.objects.select_related('source').order_by('-created_at')
    if source_id:
        ku_qs = ku_qs.filter(source_id=source_id)
    for unit in ku_qs[:10]:
        events.append(
            {
                'at': unit.created_at,
                'message': f'Knowledge imported: "{unit.title}"',
                'url_name': 'knowledge:knowledgeunit_detail',
                'url_kwargs': {'pk': unit.pk},
            }
        )

    approved_qs = KnowledgeUnit.objects.select_related('source').filter(
        governance_status=KnowledgeUnit.GovernanceStatus.APPROVED,
        reviewed_at__isnull=False,
    ).order_by('-reviewed_at')
    if source_id:
        approved_qs = approved_qs.filter(source_id=source_id)
    for unit in approved_qs[:10]:
        events.append(
            {
                'at': unit.reviewed_at,
                'message': f'Unit approved: "{unit.title}"',
                'url_name': 'knowledge:knowledgeunit_detail',
                'url_kwargs': {'pk': unit.pk},
            }
        )

    events.sort(key=lambda e: e['at'], reverse=True)
    return events[:limit]


def get_source_failures(source_id):
    failed_jobs = list(
        DocumentIngestionJob.objects.filter(
            source_id=source_id, status=DocumentIngestionJob.Status.FAILED
        ).order_by('-updated_at')[:5]
    )
    failed_batches = list(
        ExtractionBatch.objects.filter(source_id=source_id)
        .exclude(parse_error='')
        .order_by('-updated_at')[:5]
    )
    return failed_jobs, failed_batches


def get_source_detail_processing(source_id) -> SourceProcessingStats:
    stats_map = bulk_source_processing_stats([source_id])
    return stats_map.get(str(source_id)) or SourceProcessingStats(source_id=str(source_id))
