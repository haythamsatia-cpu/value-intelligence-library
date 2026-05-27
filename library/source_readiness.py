"""Computed readiness indicators for library sources."""

from ai_extraction.models import DocumentIngestionJob
from knowledge.models import KnowledgeUnit

from .models import Source


def get_source_readiness(source: Source) -> dict:
    """Return readiness flags for UI badges."""
    has_file_link = bool(
        source.source_file
        or source.file
        or (source.original_file_path and source.original_file_path.strip())
    )
    job_count = source.ingestion_jobs.count()
    extracted = source.ingestion_jobs.filter(
        status=DocumentIngestionJob.Status.EXTRACTED
    ).exists()
    chunks_exist = source.text_chunks.exists()
    batches_parsed = source.extraction_batches.filter(parsed_at__isnull=False).exists()
    has_ku = source.knowledge_units.exists()
    approved = source.knowledge_units.filter(
        governance_status=KnowledgeUnit.GovernanceStatus.APPROVED
    ).exists()

    ingestion_started = job_count > 0 or chunks_exist or source.extraction_batches.exists()
    extraction_completed = extracted or chunks_exist or batches_parsed
    review_completed = approved or source.status == Source.Status.COMPLETED

    return {
        'file_linked': has_file_link,
        'ingestion_started': ingestion_started,
        'extraction_completed': extraction_completed,
        'review_completed': review_completed,
        'labels': _readiness_labels(
            has_file_link, ingestion_started, extraction_completed, review_completed
        ),
    }


def _readiness_labels(file_linked, ingestion_started, extraction_completed, review_completed):
    labels = []
    if file_linked:
        labels.append(('file_linked', 'File linked', 'success'))
    if ingestion_started:
        labels.append(('ingestion_started', 'Ingestion started', 'info'))
    if extraction_completed:
        labels.append(('extraction_completed', 'Extraction progressed', 'primary'))
    if review_completed:
        labels.append(('review_completed', 'Review complete', 'success'))
    return labels


def annotate_sources_readiness(sources):
    """Attach .readiness dict and duplicate_warning to each source in a list."""
    from django.db.models import Count
    from django.db.models.functions import Lower

    source_list = list(sources)
    if not source_list:
        return sources

    page_titles = {s.title.strip().lower() for s in source_list if s.title.strip()}
    duplicate_titles = set()
    if page_titles:
        duplicate_titles = set(
            Source.objects.annotate(title_lower=Lower('title'))
            .filter(title_lower__in=page_titles)
            .values('title_lower')
            .annotate(c=Count('id'))
            .filter(c__gt=1)
            .values_list('title_lower', flat=True)
        )

    for source in source_list:
        source.readiness = get_source_readiness(source)
        t = source.title.strip().lower()
        source.duplicate_warning = bool(t) and t in duplicate_titles
    return sources
