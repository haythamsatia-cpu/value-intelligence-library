"""
Lightweight extraction quality warnings — never block import.
"""

FILLER_PHRASES = [
    'it is important to',
    'it is essential to',
    'in today',
    'plays a crucial role',
    'best practice is to always',
    'communication is key',
    'stakeholders are important',
    'at the end of the day',
    'holistic approach',
    'synergy',
    'leverage best practices',
    'drive value',
    'world-class',
]

GENERIC_TITLE_PATTERNS = [
    'introduction',
    'overview',
    'summary',
    'conclusion',
    'key points',
    'general principles',
]


def _template_requirements(template_settings) -> dict:
    """template_settings: ExtractionPromptTemplate or EffectiveTemplateSettings."""
    return {
        'practical_application': getattr(template_settings, 'require_practical_application', False),
        'source_traceability': getattr(template_settings, 'require_source_traceability', False),
        'page_references': getattr(template_settings, 'require_page_references', False),
        'consultant_use_case': getattr(template_settings, 'require_consultant_use_case', False),
        'threshold': getattr(template_settings, 'minimum_quality_threshold', 'medium'),
    }


def validate_extraction_item(
    item: dict,
    parsed: dict,
    *,
    template_settings=None,
    index: int | None = None,
) -> list[str]:
    """Return human-readable warning strings for one parsed item."""
    warnings: list[str] = []
    prefix = f'Item {(index or 0) + 1}' if index is not None else 'Item'

    title = parsed.get('title', '')
    if len(title) < 12:
        warnings.append(f'{prefix}: title is very short — may not be specific enough.')

    title_lower = title.lower()
    if any(p in title_lower for p in GENERIC_TITLE_PATTERNS) and len(title) < 40:
        warnings.append(f'{prefix}: title looks generic or section-heading-like.')

    insight = (parsed.get('executive_insight') or '') + ' ' + (parsed.get('detailed_explanation') or '')
    insight_lower = insight.lower()
    if len(insight.strip()) < 40 and _threshold(template_settings) != 'low':
        warnings.append(f'{prefix}: executive/detailed insight is thin or missing.')

    for phrase in FILLER_PHRASES:
        if phrase in insight_lower:
            warnings.append(f'{prefix}: possible filler phrase detected ("{phrase}").')
            break

    reqs = _template_requirements(template_settings) if template_settings else {}
    if reqs.get('practical_application') and not parsed.get('practical_application', '').strip():
        warnings.append(f'{prefix}: missing practical_application (required by template).')

    trace = (
        parsed.get('source_traceability_note', '')
        or parsed.get('source_quote_short', '')
        or parsed.get('citation', '')
    )
    if reqs.get('source_traceability') and not trace.strip():
        warnings.append(f'{prefix}: missing source traceability (quote, citation, or traceability note).')

    if reqs.get('page_references') and not (
        parsed.get('page_reference', '').strip() or _normalize_page_from_item(item)
    ):
        warnings.append(f'{prefix}: missing page_reference (required by template).')

    combined_len = sum(
        len(parsed.get(k, '') or '')
        for k in (
            'executive_insight', 'detailed_explanation', 'practical_application',
            'consultant_use_case', 'course_use_case',
        )
    )
    if combined_len > 12000:
        warnings.append(f'{prefix}: very long combined text — consider splitting into atomic units.')

    return warnings


def _threshold(template_settings) -> str:
    if not template_settings:
        return 'medium'
    return getattr(template_settings, 'minimum_quality_threshold', 'medium') or 'medium'


def _normalize_page_from_item(item: dict) -> str:
    return str(item.get('page_reference', '') or '').strip()


def append_quality_warnings_to_notes(parsed: dict, warnings: list[str]) -> None:
    if not warnings:
        return
    existing = parsed.get('reviewer_notes', '').strip()
    block = 'Quality warnings: ' + '; '.join(warnings)
    parsed['reviewer_notes'] = f'{existing}; {block}'.strip('; ') if existing else block
    parsed['quality_warnings'] = warnings
