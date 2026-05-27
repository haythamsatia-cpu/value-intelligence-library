import re

from django.contrib import messages

from knowledge.models import KnowledgeUnit

from .models import ExtractionCandidate


def _page_reference_from_notes(notes: str) -> str:
    match = re.search(r'Page reference:\s*([^;]+)', notes or '', re.IGNORECASE)
    return match.group(1).strip()[:100] if match else ''


def find_similar_knowledge_units(title: str, limit: int = 5) -> list[KnowledgeUnit]:
    """Find existing knowledge units with very similar titles (case-insensitive / substring)."""
    title_norm = title.strip().lower()
    if len(title_norm) < 4:
        return []

    similar = []
    seen_ids = set()
    exact = KnowledgeUnit.objects.filter(title__iexact=title).only('id', 'title')[:limit]
    for unit in exact:
        similar.append(unit)
        seen_ids.add(unit.pk)

    if len(similar) >= limit:
        return similar

    for unit in KnowledgeUnit.objects.only('id', 'title').order_by('-updated_at')[:500]:
        if unit.pk in seen_ids:
            continue
        t = unit.title.strip().lower()
        if len(t) < 4:
            continue
        if title_norm == t or title_norm in t or t in title_norm:
            similar.append(unit)
            seen_ids.add(unit.pk)
        if len(similar) >= limit:
            break
    return similar


def import_candidate_to_knowledge_unit(
    candidate: ExtractionCandidate,
    *,
    warn_similar: bool = True,
) -> tuple[KnowledgeUnit | None, list[KnowledgeUnit]]:
    """
    Create a KnowledgeUnit from an extraction candidate.
    Returns (unit or None, list of similar existing units for warnings).
    """
    similar_units: list[KnowledgeUnit] = []
    if warn_similar:
        similar_units = find_similar_knowledge_units(candidate.title)

    if candidate.import_status == ExtractionCandidate.ImportStatus.IMPORTED:
        return candidate.imported_knowledge_unit, similar_units

    domain = candidate.resolve_domain()
    if not domain:
        return None, similar_units

    batch = candidate.batch
    knowledge_type = (
        candidate.proposed_knowledge_type or KnowledgeUnit.KnowledgeType.OTHER
    )

    page_reference = _page_reference_from_notes(candidate.reviewer_notes)
    approval_notes = ''
    if candidate.reviewer_notes and (
        'Quality warnings' in candidate.reviewer_notes
        or 'Unresolved taxonomy' in candidate.reviewer_notes
        or 'Page reference' in candidate.reviewer_notes
    ):
        approval_notes = candidate.reviewer_notes

    unit = KnowledgeUnit.objects.create(
        title=candidate.title,
        domain=domain,
        subdomain=candidate.proposed_subdomain,
        topic=candidate.proposed_topic,
        concept=candidate.proposed_concept,
        source=batch.source,
        chapter=batch.chapter,
        page_reference=page_reference,
        knowledge_type=knowledge_type,
        executive_insight=candidate.executive_insight,
        detailed_explanation=candidate.detailed_explanation,
        practical_application=candidate.practical_application,
        consultant_use_case=candidate.consultant_use_case,
        course_use_case=candidate.course_use_case,
        common_mistakes=candidate.common_mistakes,
        warning_signs=candidate.warning_signs,
        best_practices=candidate.best_practices,
        example=candidate.example,
        keywords=candidate.keywords,
        citation=candidate.citation,
        source_quote_short=candidate.source_quote_short,
        review_status=KnowledgeUnit.ReviewStatus.AI_EXTRACTED,
        governance_status=KnowledgeUnit.GovernanceStatus.PENDING_REVIEW,
        confidence_level=KnowledgeUnit.ValueLevel.MEDIUM,
        source_quality=KnowledgeUnit.ValueLevel.MEDIUM,
        would_i_use_this=True,
        imported_from_batch=batch,
        imported_via=KnowledgeUnit.ImportedVia.CANDIDATE_REVIEW,
        approval_notes=approval_notes,
    )

    candidate.import_status = ExtractionCandidate.ImportStatus.IMPORTED
    candidate.imported_knowledge_unit = unit
    candidate.save(update_fields=['import_status', 'imported_knowledge_unit', 'updated_at'])
    return unit, similar_units


def reject_candidate(candidate: ExtractionCandidate) -> None:
    candidate.import_status = ExtractionCandidate.ImportStatus.REJECTED
    candidate.save(update_fields=['import_status', 'updated_at'])


def bulk_import_candidates(candidate_ids: list) -> dict:
    """Import multiple pending candidates. Returns counts and messages."""
    stats = {'imported': 0, 'failed': 0, 'skipped': 0, 'warnings': []}
    qs = ExtractionCandidate.objects.filter(
        pk__in=candidate_ids,
        import_status=ExtractionCandidate.ImportStatus.PENDING,
    ).select_related('batch', 'batch__source')
    for candidate in qs:
        unit, similar = import_candidate_to_knowledge_unit(candidate)
        if unit:
            stats['imported'] += 1
            if similar:
                stats['warnings'].append(
                    f'"{candidate.title}" — similar existing: '
                    + ', '.join(u.title[:60] for u in similar[:3])
                )
        else:
            stats['failed'] += 1
    stats['skipped'] = len(candidate_ids) - qs.count()
    return stats


def bulk_reject_candidates(candidate_ids: list) -> int:
    updated = ExtractionCandidate.objects.filter(
        pk__in=candidate_ids,
        import_status=ExtractionCandidate.ImportStatus.PENDING,
    ).update(import_status=ExtractionCandidate.ImportStatus.REJECTED)
    return updated


def flash_import_result(request, unit, candidate, similar_units=None):
    if unit:
        msg = f'Imported "{candidate.title}" as knowledge unit (AI extracted, pending review).'
        if similar_units:
            titles = '; '.join(f'"{u.title}"' for u in similar_units[:3])
            messages.warning(
                request,
                f'Similar knowledge unit(s) already exist: {titles}. Review for duplicates.',
            )
        messages.success(request, msg)
    else:
        messages.error(
            request,
            'Cannot import: set a proposed domain on the candidate, or assign a primary domain on the batch source.',
        )
