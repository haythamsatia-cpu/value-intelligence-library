"""Source-level review workspace queries, filters, metrics, and pipeline."""

from django.db.models import Q

from ai_extraction.models import ExtractionBatch, ExtractionCandidate
from knowledge.models import KnowledgeUnit

from .models import Source
from .processing import get_source_detail_processing

WORKSPACE_TABS = [
    ('candidates', 'Candidates'),
    ('imported', 'Imported Knowledge Units'),
    ('pending_review', 'Pending Review'),
    ('approved', 'Approved'),
    ('rejected_archived', 'Rejected/Archived'),
    ('duplicates', 'Duplicates'),
]

REVIEW_PIPELINE_KEYS = [
    ('extracted', 'PDF extracted'),
    ('chunked', 'Chunks'),
    ('batches', 'Batches'),
    ('parsed', 'Parsed'),
    ('imported', 'Imported'),
    ('reviewed', 'Reviewed'),
    ('approved', 'Approved'),
]


def source_knowledge_queryset(source: Source):
    """Knowledge units linked to source directly or via batch import."""
    return (
        KnowledgeUnit.objects.filter(
            Q(source=source) | Q(imported_from_batch__source=source)
        )
        .select_related(
            'domain',
            'subdomain',
            'topic',
            'concept',
            'source',
            'imported_from_batch',
            'reviewed_by',
        )
        .prefetch_related('tags')
        .distinct()
    )


def source_candidates_queryset(source: Source):
    return (
        ExtractionCandidate.objects.filter(batch__source=source)
        .select_related(
            'batch',
            'proposed_domain',
            'proposed_subdomain',
            'proposed_topic',
            'proposed_concept',
            'imported_knowledge_unit',
        )
        .prefetch_related('batch__text_chunks')
        .order_by('-created_at')
    )


def apply_knowledge_tab(qs, tab: str):
    if tab == 'imported':
        return qs
    if tab == 'pending_review':
        return qs.filter(governance_status=KnowledgeUnit.GovernanceStatus.PENDING_REVIEW)
    if tab == 'approved':
        return qs.filter(governance_status=KnowledgeUnit.GovernanceStatus.APPROVED)
    if tab == 'rejected_archived':
        return qs.filter(
            Q(governance_status=KnowledgeUnit.GovernanceStatus.ARCHIVED)
            | Q(review_status=KnowledgeUnit.ReviewStatus.REJECTED)
            | Q(review_status=KnowledgeUnit.ReviewStatus.ARCHIVED)
        )
    if tab == 'duplicates':
        return qs.filter(is_duplicate=True)
    return qs


def apply_candidate_filters(request, qs):
    batch_id = request.GET.get('batch', '').strip()
    if batch_id:
        qs = qs.filter(batch_id=batch_id)
    import_status = request.GET.get('import_status', '').strip()
    if import_status in dict(ExtractionCandidate.ImportStatus.choices):
        qs = qs.filter(import_status=import_status)
    knowledge_type = request.GET.get('knowledge_type', '').strip()
    if knowledge_type in dict(KnowledgeUnit.KnowledgeType.choices):
        qs = qs.filter(proposed_knowledge_type=knowledge_type)
    domain_id = request.GET.get('domain', '').strip()
    if domain_id:
        qs = qs.filter(proposed_domain_id=domain_id)
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(executive_insight__icontains=q)
            | Q(detailed_explanation__icontains=q)
            | Q(practical_application__icontains=q)
            | Q(keywords__icontains=q)
        )
    page_from = request.GET.get('page_from', '').strip()
    page_to = request.GET.get('page_to', '').strip()
    if page_from.isdigit():
        qs = qs.filter(batch__text_chunks__start_page__gte=int(page_from))
    if page_to.isdigit():
        qs = qs.filter(batch__text_chunks__end_page__lte=int(page_to))
    return qs.distinct()


def apply_knowledge_filters(request, qs):
    batch_id = request.GET.get('batch', '').strip()
    if batch_id:
        qs = qs.filter(imported_from_batch_id=batch_id)
    domain_id = request.GET.get('domain', '').strip()
    if domain_id:
        qs = qs.filter(domain_id=domain_id)
    subdomain_id = request.GET.get('subdomain', '').strip()
    if subdomain_id:
        qs = qs.filter(subdomain_id=subdomain_id)
    topic_id = request.GET.get('topic', '').strip()
    if topic_id:
        qs = qs.filter(topic_id=topic_id)
    concept_id = request.GET.get('concept', '').strip()
    if concept_id:
        qs = qs.filter(concept_id=concept_id)
    knowledge_type = request.GET.get('knowledge_type', '').strip()
    if knowledge_type in dict(KnowledgeUnit.KnowledgeType.choices):
        qs = qs.filter(knowledge_type=knowledge_type)
    review_status = request.GET.get('review_status', '').strip()
    if review_status in dict(KnowledgeUnit.ReviewStatus.choices):
        qs = qs.filter(review_status=review_status)
    governance_status = request.GET.get('governance_status', '').strip()
    if governance_status in dict(KnowledgeUnit.GovernanceStatus.choices):
        qs = qs.filter(governance_status=governance_status)
    imported_via = request.GET.get('imported_via', '').strip()
    if imported_via in dict(KnowledgeUnit.ImportedVia.choices):
        qs = qs.filter(imported_via=imported_via)
    confidence = request.GET.get('confidence', '').strip()
    if confidence in dict(KnowledgeUnit.ValueLevel.choices):
        qs = qs.filter(confidence_level=confidence)
    duplicate_flag = request.GET.get('duplicate', '').strip()
    if duplicate_flag == 'yes':
        qs = qs.filter(is_duplicate=True)
    elif duplicate_flag == 'no':
        qs = qs.filter(is_duplicate=False)
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(executive_insight__icontains=q)
            | Q(detailed_explanation__icontains=q)
            | Q(practical_application__icontains=q)
            | Q(keywords__icontains=q)
            | Q(page_reference__icontains=q)
        )
    page_from = request.GET.get('page_from', '').strip()
    page_to = request.GET.get('page_to', '').strip()
    if page_from.isdigit():
        qs = qs.filter(page_reference__regex=rf'\b{page_from}\b|^{page_from}')
    if page_to.isdigit():
        qs = qs.filter(page_reference__regex=rf'\b{page_to}\b')
    return qs.order_by('-updated_at')


def get_review_workspace_metrics(source: Source) -> dict:
    candidates = ExtractionCandidate.objects.filter(batch__source=source)
    units = source_knowledge_queryset(source)
    total_candidates = candidates.count()
    pending_candidates = candidates.filter(
        import_status=ExtractionCandidate.ImportStatus.PENDING
    ).count()
    imported_units = units.count()
    pending_review = units.filter(
        governance_status=KnowledgeUnit.GovernanceStatus.PENDING_REVIEW
    ).count()
    approved_units = units.filter(
        governance_status=KnowledgeUnit.GovernanceStatus.APPROVED
    ).count()
    archived_units = units.filter(
        Q(governance_status=KnowledgeUnit.GovernanceStatus.ARCHIVED)
        | Q(review_status__in=[
            KnowledgeUnit.ReviewStatus.REJECTED,
            KnowledgeUnit.ReviewStatus.ARCHIVED,
        ])
    ).count()
    rejected_candidates = candidates.filter(
        import_status=ExtractionCandidate.ImportStatus.REJECTED
    ).count()
    duplicate_suspects = units.filter(is_duplicate=True).count()
    approval_ratio = (
        round(approved_units * 100 / imported_units) if imported_units else 0
    )
    return {
        'total_candidates': total_candidates,
        'pending_candidates': pending_candidates,
        'imported_units': imported_units,
        'pending_review_units': pending_review,
        'approved_units': approved_units,
        'archived_rejected': archived_units + rejected_candidates,
        'rejected_candidates': rejected_candidates,
        'duplicate_suspects': duplicate_suspects,
        'approval_ratio': approval_ratio,
    }


def get_review_workspace_pipeline(source: Source) -> list[dict]:
    stats = get_source_detail_processing(source.pk)
    by_key = {stage['key']: stage for stage in stats.pipeline}
    pipeline = []
    for key, label in REVIEW_PIPELINE_KEYS:
        stage = by_key.get(key, {'pct': 0, 'state': 'pending'})
        pipeline.append(
            {
                'key': key,
                'label': label,
                'pct': stage.get('pct', 0),
                'state': stage.get('state', 'pending'),
            }
        )
    return pipeline


def candidate_page_reference(candidate: ExtractionCandidate) -> str:
    chunk = candidate.batch.text_chunks.first()
    if not chunk or not chunk.start_page:
        return ''
    if chunk.end_page and chunk.end_page != chunk.start_page:
        return f'p.{chunk.start_page}–{chunk.end_page}'
    return f'p.{chunk.start_page}'


def workspace_filter_context(request, source: Source) -> dict:
    return {
        'tab': request.GET.get('tab', 'candidates'),
        'query': request.GET.get('q', ''),
        'filter_batch': request.GET.get('batch', ''),
        'filter_domain': request.GET.get('domain', ''),
        'filter_subdomain': request.GET.get('subdomain', ''),
        'filter_topic': request.GET.get('topic', ''),
        'filter_concept': request.GET.get('concept', ''),
        'filter_knowledge_type': request.GET.get('knowledge_type', ''),
        'filter_review_status': request.GET.get('review_status', ''),
        'filter_governance_status': request.GET.get('governance_status', ''),
        'filter_imported_via': request.GET.get('imported_via', ''),
        'filter_confidence': request.GET.get('confidence', ''),
        'filter_duplicate': request.GET.get('duplicate', ''),
        'filter_import_status': request.GET.get('import_status', ''),
        'filter_page_from': request.GET.get('page_from', ''),
        'filter_page_to': request.GET.get('page_to', ''),
        'batches': ExtractionBatch.objects.filter(source=source).order_by('-updated_at'),
        'tab_counts': _tab_counts(source),
    }


def _tab_counts(source: Source) -> dict:
    candidates = ExtractionCandidate.objects.filter(batch__source=source)
    units = source_knowledge_queryset(source)
    return {
        'candidates': candidates.count(),
        'imported': units.count(),
        'pending_review': units.filter(
            governance_status=KnowledgeUnit.GovernanceStatus.PENDING_REVIEW
        ).count(),
        'approved': units.filter(
            governance_status=KnowledgeUnit.GovernanceStatus.APPROVED
        ).count(),
        'rejected_archived': (
            units.filter(
                Q(governance_status=KnowledgeUnit.GovernanceStatus.ARCHIVED)
                | Q(review_status__in=[
                    KnowledgeUnit.ReviewStatus.REJECTED,
                    KnowledgeUnit.ReviewStatus.ARCHIVED,
                ])
            ).count()
            + candidates.filter(import_status=ExtractionCandidate.ImportStatus.REJECTED).count()
        ),
        'duplicates': units.filter(is_duplicate=True).count(),
    }
