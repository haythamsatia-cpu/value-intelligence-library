"""Queryset filters, metrics, and bulk updates for the taxonomy cleanup workflow."""

from django.db.models import Q
from django.utils.dateparse import parse_date

from taxonomy.models import Concept, Subdomain, Topic
from taxonomy.utils import get_or_create_uncategorized_domain

from .models import KnowledgeUnit

CLEANUP_MODES = [
    ('', 'Needs cleanup (default)'),
    ('uncategorized', 'Uncategorized'),
    ('missing_subdomain', 'Missing Subdomain'),
    ('missing_topic', 'Missing Topic'),
    ('missing_concept', 'Missing Concept'),
    ('fast_imported', 'Fast Imported'),
    ('pending_review', 'Pending Review'),
    ('high_consulting', 'High Consulting Value'),
    ('all', 'All units (no scope)'),
]

QUICK_BULK_ACTIONS = {
    'set_reviewed': 'bulk_set_reviewed',
    'set_approved': 'bulk_approve',
    'mark_duplicate': 'bulk_mark_duplicate',
    'archive_selected': 'bulk_archive',
}


def _default_cleanup_scope(qs):
    uncategorized = get_or_create_uncategorized_domain()
    return qs.filter(
        Q(domain=uncategorized)
        | Q(subdomain__isnull=True)
        | Q(topic__isnull=True)
        | Q(concept__isnull=True)
    )


def apply_cleanup_mode(qs, mode: str):
    if mode == 'uncategorized':
        return qs.filter(domain=get_or_create_uncategorized_domain())
    if mode == 'missing_subdomain':
        return qs.filter(subdomain__isnull=True)
    if mode == 'missing_topic':
        return qs.filter(topic__isnull=True)
    if mode == 'missing_concept':
        return qs.filter(concept__isnull=True)
    if mode == 'fast_imported':
        return qs.filter(imported_via=KnowledgeUnit.ImportedVia.FAST_IMPORT)
    if mode == 'pending_review':
        return qs.filter(governance_status=KnowledgeUnit.GovernanceStatus.PENDING_REVIEW)
    if mode == 'high_consulting':
        return qs.filter(consulting_value=KnowledgeUnit.ValueLevel.HIGH)
    if mode == 'all':
        return qs
    return _default_cleanup_scope(qs)


def apply_taxonomy_cleanup_filters(request, qs):
    """Apply GET filters on top of the cleanup scope/mode queryset."""
    subdomain_id = request.GET.get('subdomain')
    if subdomain_id:
        qs = qs.filter(subdomain_id=subdomain_id)
    topic_id = request.GET.get('topic')
    if topic_id:
        qs = qs.filter(topic_id=topic_id)
    concept_id = request.GET.get('concept')
    if concept_id:
        qs = qs.filter(concept_id=concept_id)
    imported_via = request.GET.get('imported_via')
    if imported_via in dict(KnowledgeUnit.ImportedVia.choices):
        qs = qs.filter(imported_via=imported_via)
    knowledge_type = request.GET.get('knowledge_type')
    if knowledge_type in dict(KnowledgeUnit.KnowledgeType.choices):
        qs = qs.filter(knowledge_type=knowledge_type)

    created_from = parse_date(request.GET.get('created_from', '') or '')
    if created_from:
        qs = qs.filter(created_at__date__gte=created_from)
    created_to = parse_date(request.GET.get('created_to', '') or '')
    if created_to:
        qs = qs.filter(created_at__date__lte=created_to)

    ordering = request.GET.get('ordering', '-created_at')
    ordering_map = {
        '-created_at': '-created_at',
        'created_at': 'created_at',
        '-updated_at': '-updated_at',
        'title': 'title',
        'consulting_value': 'consulting_value',
        'teaching_value': 'teaching_value',
    }
    return qs.order_by(ordering_map.get(ordering, '-created_at'))


def get_taxonomy_cleanup_queryset(request, base_qs):
    mode = request.GET.get('mode', '')
    qs = apply_cleanup_mode(base_qs, mode)
    return apply_taxonomy_cleanup_filters(request, qs)


def get_cleanup_summary_metrics():
    """Global counts for summary cards (not limited to current page filter)."""
    base = KnowledgeUnit.objects.all()
    uncategorized = get_or_create_uncategorized_domain()
    return {
        'uncategorized': base.filter(domain=uncategorized).count(),
        'missing_subdomain': base.filter(subdomain__isnull=True).count(),
        'missing_topic': base.filter(topic__isnull=True).count(),
        'missing_concept': base.filter(concept__isnull=True).count(),
        'fast_imported': base.filter(imported_via=KnowledgeUnit.ImportedVia.FAST_IMPORT).count(),
        'pending_review': base.filter(
            governance_status=KnowledgeUnit.GovernanceStatus.PENDING_REVIEW
        ).count(),
    }


def apply_taxonomy_cleanup_bulk_update(request, queryset) -> list[str]:
    """
    Update only POST fields that have a value (empty = leave unchanged).
    Returns list of success message fragments.
    """
    messages_out = []
    update_fields = {}

    domain_id = request.POST.get('bulk_domain', '').strip()
    if domain_id:
        update_fields['domain_id'] = domain_id

    subdomain_id = request.POST.get('bulk_subdomain', '').strip()
    if subdomain_id:
        update_fields['subdomain_id'] = subdomain_id

    topic_id = request.POST.get('bulk_topic', '').strip()
    if topic_id:
        update_fields['topic_id'] = topic_id

    concept_id = request.POST.get('bulk_concept', '').strip()
    if concept_id:
        update_fields['concept_id'] = concept_id

    knowledge_type = request.POST.get('bulk_knowledge_type', '').strip()
    if knowledge_type in dict(KnowledgeUnit.KnowledgeType.choices):
        update_fields['knowledge_type'] = knowledge_type

    for field_name, post_key in (
        ('consulting_value', 'bulk_consulting_value'),
        ('teaching_value', 'bulk_teaching_value'),
        ('confidence_level', 'bulk_confidence_level'),
        ('source_quality', 'bulk_source_quality'),
    ):
        value = request.POST.get(post_key, '').strip()
        if value in dict(KnowledgeUnit.ValueLevel.choices):
            update_fields[field_name] = value

    governance_status = request.POST.get('bulk_governance_status', '').strip()
    if governance_status in dict(KnowledgeUnit.GovernanceStatus.choices):
        update_fields['governance_status'] = governance_status
        if governance_status == KnowledgeUnit.GovernanceStatus.APPROVED:
            update_fields['review_status'] = KnowledgeUnit.ReviewStatus.APPROVED
        elif governance_status == KnowledgeUnit.GovernanceStatus.REVIEWED:
            update_fields['review_status'] = KnowledgeUnit.ReviewStatus.REVIEWED
        elif governance_status == KnowledgeUnit.GovernanceStatus.ARCHIVED:
            update_fields['review_status'] = KnowledgeUnit.ReviewStatus.ARCHIVED
        elif governance_status == KnowledgeUnit.GovernanceStatus.PENDING_REVIEW:
            update_fields['review_status'] = KnowledgeUnit.ReviewStatus.AI_EXTRACTED

    if update_fields:
        count = queryset.update(**update_fields)
        messages_out.append(f'Updated fields on {count} unit(s).')

    tag_ids = request.POST.getlist('bulk_tags')
    if tag_ids:
        from taxonomy.models import Tag

        tags = list(Tag.objects.filter(pk__in=tag_ids))
        if tags:
            tagged = 0
            for unit in queryset:
                unit.tags.add(*tags)
                tagged += 1
            messages_out.append(f'Added tag(s) to {tagged} unit(s).')

    if not messages_out:
        messages_out.append('No taxonomy fields selected — nothing changed.')
    return messages_out


def taxonomy_cleanup_filter_context(request):
    """Shared template context for filter form state."""
    return {
        'mode': request.GET.get('mode', ''),
        'cleanup_modes': CLEANUP_MODES,
        'query': request.GET.get('q', '').strip(),
        'ordering': request.GET.get('ordering', '-created_at'),
        'filter_domain': request.GET.get('domain', ''),
        'filter_source': request.GET.get('source', ''),
        'filter_subdomain': request.GET.get('subdomain', ''),
        'filter_topic': request.GET.get('topic', ''),
        'filter_concept': request.GET.get('concept', ''),
        'filter_review_status': request.GET.get('review_status', ''),
        'filter_governance_status': request.GET.get('governance_status', ''),
        'filter_imported_via': request.GET.get('imported_via', ''),
        'filter_knowledge_type': request.GET.get('knowledge_type', ''),
        'filter_consulting_value': request.GET.get('consulting_value', ''),
        'filter_teaching_value': request.GET.get('teaching_value', ''),
        'filter_created_from': request.GET.get('created_from', ''),
        'filter_created_to': request.GET.get('created_to', ''),
        'subdomains': Subdomain.objects.select_related('domain').order_by('domain__name', 'name'),
        'topics': Topic.objects.select_related('subdomain__domain').order_by(
            'subdomain__domain__name', 'subdomain__name', 'name'
        ),
        'concepts': Concept.objects.select_related('topic__subdomain__domain').order_by(
            'topic__subdomain__domain__name', 'topic__subdomain__name', 'topic__name', 'name'
        ),
    }
