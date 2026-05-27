"""Per-batch extraction and governance quality metrics."""

from django.db.models import Avg, Count, Q

from knowledge.models import KnowledgeUnit

from .models import ExtractionCandidate


def get_batch_quality_metrics(batch) -> dict:
    candidates = batch.candidates.all()
    total = candidates.count()
    imported = candidates.filter(import_status=ExtractionCandidate.ImportStatus.IMPORTED).count()
    rejected = candidates.filter(import_status=ExtractionCandidate.ImportStatus.REJECTED).count()
    pending = candidates.filter(import_status=ExtractionCandidate.ImportStatus.PENDING).count()

    imported_units = KnowledgeUnit.objects.filter(
        Q(extraction_candidates__batch=batch)
        | Q(imported_from_batch=batch)
    ).distinct()

    ku_count = imported_units.count()
    approved = imported_units.filter(
        governance_status=KnowledgeUnit.GovernanceStatus.APPROVED
    ).count()
    duplicates = imported_units.filter(is_duplicate=True).count()
    pending_review = imported_units.filter(
        governance_status=KnowledgeUnit.GovernanceStatus.PENDING_REVIEW
    ).count()

    avg_confidence = imported_units.aggregate(
        avg=Avg('confidence_level')
    )['avg']  # CharField — count medium/high instead

    confidence_breakdown = list(
        imported_units.values('confidence_level').annotate(c=Count('id'))
    )

    approval_ratio = int(approved * 100 / ku_count) if ku_count else 0
    duplicate_ratio = int(duplicates * 100 / ku_count) if ku_count else 0
    rejection_ratio = int(rejected * 100 / total) if total else 0
    import_ratio = int(imported * 100 / total) if total else 0

    return {
        'candidate_count': total,
        'candidates_pending': pending,
        'candidates_imported': imported,
        'candidates_rejected': rejected,
        'imported_units_count': ku_count,
        'approved_units_count': approved,
        'pending_review_count': pending_review,
        'duplicate_suspects_count': duplicates,
        'approval_ratio': approval_ratio,
        'duplicate_ratio': duplicate_ratio,
        'review_rejection_ratio': rejection_ratio,
        'candidate_import_ratio': import_ratio,
        'confidence_breakdown': confidence_breakdown,
        'avg_confidence_label': _dominant_confidence(confidence_breakdown),
    }


def _dominant_confidence(breakdown: list) -> str:
    if not breakdown:
        return '—'
    top = max(breakdown, key=lambda x: x['c'])
    return top.get('confidence_level') or '—'
