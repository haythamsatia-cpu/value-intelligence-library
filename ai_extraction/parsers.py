"""
Parse Claude JSON output into ExtractionCandidate or KnowledgeUnit records.
No external API calls — operates on batch.ai_output_raw only.
"""
import json
import re
from dataclasses import dataclass, field
from typing import Any

from django.db import transaction
from django.utils import timezone

from knowledge.models import KnowledgeUnit
from taxonomy.models import Concept, Domain, Subdomain, Topic
from taxonomy.utils import get_or_create_uncategorized_domain

from .json_schema import OPTIONAL_EXTENDED_JSON_KEYS
from .models import ExtractionBatch, ExtractionCandidate
from .quality_profiles import EffectiveTemplateSettings
from .quality_validation import append_quality_warnings_to_notes, validate_extraction_item

TEXT_FIELDS = [
    'executive_insight', 'detailed_explanation', 'practical_application',
    'consultant_use_case', 'course_use_case', 'common_mistakes', 'warning_signs',
    'best_practices', 'example', 'keywords', 'citation', 'source_quote_short',
]

VALID_KNOWLEDGE_TYPES = {choice[0] for choice in KnowledgeUnit.KnowledgeType.choices}


@dataclass
class ParsePreview:
    created: int = 0
    skipped_duplicates: int = 0
    skipped_invalid: int = 0
    quality_warnings: int = 0
    errors: list[str] = field(default_factory=list)

    def summary_lines(self) -> list[str]:
        lines = [
            f'Candidates created: {self.created}',
            f'Skipped (duplicate title in batch): {self.skipped_duplicates}',
            f'Skipped (invalid entries): {self.skipped_invalid}',
            f'Quality warnings (non-blocking): {self.quality_warnings}',
        ]
        if self.errors:
            lines.append('Validation / parse errors:')
            lines.extend(f'  - {e}' for e in self.errors[:50])
            if len(self.errors) > 50:
                lines.append(f'  ... and {len(self.errors) - 50} more')
        return lines


@dataclass
class FastImportPreview:
    created: int = 0
    skipped_duplicates: int = 0
    skipped_similar: int = 0
    flagged_similar: int = 0
    skipped_invalid: int = 0
    quality_warnings: int = 0
    errors: list[str] = field(default_factory=list)

    def summary_lines(self) -> list[str]:
        lines = [
            f'Knowledge units created: {self.created}',
            f'Skipped (exact duplicate title in library): {self.skipped_duplicates}',
            f'Skipped (invalid entries): {self.skipped_invalid}',
            f'Quality warnings (non-blocking): {self.quality_warnings}',
        ]
        if self.flagged_similar:
            lines.append(f'Imported with similar-title warning (review queue): {self.flagged_similar}')
        if self.skipped_similar:
            lines.append(f'Noted similar titles (informational): {self.skipped_similar}')
        if self.errors:
            lines.append('Validation / parse errors:')
            lines.extend(f'  - {e}' for e in self.errors[:50])
            if len(self.errors) > 50:
                lines.append(f'  ... and {len(self.errors) - 50} more')
        return lines


def extract_json_array(raw: str) -> list[Any]:
    """Extract a JSON array from raw text, tolerating markdown code fences."""
    text = raw.strip()
    if not text:
        raise ValueError('AI output is empty.')

    fence_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text, re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find('[')
        end = text.rfind(']')
        if start == -1 or end == -1 or end <= start:
            raise ValueError('Could not find a JSON array in the AI output.') from None
        data = json.loads(text[start : end + 1])

    if not isinstance(data, list):
        raise ValueError('JSON root must be an array of knowledge unit objects.')

    return data


def _normalize_str(value: Any) -> str:
    if value is None:
        return ''
    return str(value).strip()


def _resolve_domain(name: str) -> Domain | None:
    if not name:
        return None
    return Domain.objects.filter(name__iexact=name).first()


def _resolve_subdomain(name: str, domain: Domain | None) -> Subdomain | None:
    if not name:
        return None
    return Subdomain.objects.filter(domain=domain, name__iexact=name).first()


def _resolve_topic(name: str, subdomain: Subdomain | None) -> Topic | None:
    if not name:
        return None
    return Topic.objects.filter(subdomain=subdomain, name__iexact=name).first()


def _resolve_concept(name: str, topic: Topic | None) -> Concept | None:
    if not name:
        return None
    return Concept.objects.filter(topic=topic, name__iexact=name).first()


def _resolve_knowledge_type(value: str) -> str:
    normalized = value.strip().lower().replace(' ', '_').replace('-', '_')
    if normalized in VALID_KNOWLEDGE_TYPES:
        return normalized
    for choice_value, choice_label in KnowledgeUnit.KnowledgeType.choices:
        if normalized == choice_label.lower().replace(' ', '_'):
            return choice_value
    return ''


def _parse_extended_fields(item: dict) -> dict:
    extended = {}
    for key in OPTIONAL_EXTENDED_JSON_KEYS:
        extended[key] = _normalize_str(item.get(key))
    return extended


def _merge_extended_into_parsed(parsed: dict) -> None:
    """Fold optional extended JSON into storable fields without breaking older parsers."""
    page = parsed.get('page_reference', '').strip()
    if page:
        note = f'Page reference: {page}'
        parsed['reviewer_notes'] = (
            f"{note}; {parsed.get('reviewer_notes', '')}".strip('; ')
            if parsed.get('reviewer_notes')
            else note
        )
    trace = parsed.get('source_traceability_note', '').strip()
    if trace and not parsed.get('citation'):
        parsed['citation'] = trace[:2000]
    supplements = []
    for key in (
        'operational_implication',
        'contractual_implication',
        'financial_implication',
        'schedule_implication',
        'field_application',
        'risk_if_ignored',
    ):
        val = parsed.get(key, '').strip()
        if val:
            label = key.replace('_', ' ').title()
            supplements.append(f'{label}: {val}')
    if supplements:
        block = '\n'.join(supplements)
        existing = parsed.get('detailed_explanation', '')
        parsed['detailed_explanation'] = f'{existing}\n\n{block}'.strip() if existing else block


def _parse_item(
    item: dict,
    index: int,
    *,
    template_settings=None,
) -> tuple[dict | None, str | None]:
    """Validate one JSON object; return normalized field dict or error message."""
    if not isinstance(item, dict):
        return None, f'Item {index + 1}: expected an object, got {type(item).__name__}.'

    title = _normalize_str(item.get('title'))
    if not title:
        return None, f'Item {index + 1}: missing required "title".'

    domain_name = _normalize_str(item.get('domain'))
    subdomain_name = _normalize_str(item.get('subdomain'))
    topic_name = _normalize_str(item.get('topic'))
    concept_name = _normalize_str(item.get('concept'))

    domain = _resolve_domain(domain_name)
    subdomain = _resolve_subdomain(subdomain_name, domain)
    topic = _resolve_topic(topic_name, subdomain)
    concept = _resolve_concept(concept_name, topic)

    unresolved = []
    if domain_name and not domain:
        unresolved.append(f'domain "{domain_name}"')
    if subdomain_name and not subdomain:
        unresolved.append(f'subdomain "{subdomain_name}"')
    if topic_name and not topic:
        unresolved.append(f'topic "{topic_name}"')
    if concept_name and not concept:
        unresolved.append(f'concept "{concept_name}"')

    fields = {
        'title': title[:500],
        'domain': domain,
        'subdomain': subdomain,
        'topic': topic,
        'concept': concept,
        'knowledge_type': _resolve_knowledge_type(_normalize_str(item.get('knowledge_type'))),
    }
    for key in TEXT_FIELDS:
        val = _normalize_str(item.get(key))
        fields[key] = val[:500] if key == 'keywords' else val

    fields.update(_parse_extended_fields(item))

    note_parts = []
    if unresolved:
        note_parts.append('Unresolved taxonomy (left blank): ' + ', '.join(unresolved))
    kt = _normalize_str(item.get('knowledge_type'))
    if kt and not fields['knowledge_type']:
        note_parts.append(f'Unknown knowledge_type "{kt}" — left blank.')
    if note_parts:
        fields['reviewer_notes'] = '; '.join(note_parts)

    _merge_extended_into_parsed(fields)
    warnings = validate_extraction_item(item, fields, template_settings=template_settings, index=index)
    if warnings:
        append_quality_warnings_to_notes(fields, warnings)

    return fields, None


def _candidate_exists(batch: ExtractionBatch, title: str) -> bool:
    return batch.candidates.filter(title__iexact=title).exists()


def _knowledge_unit_exact_exists(title: str) -> bool:
    return KnowledgeUnit.objects.filter(title__iexact=title).exists()


def _has_similar_knowledge_unit(title: str) -> bool:
    from .services import find_similar_knowledge_units

    return bool(find_similar_knowledge_units(title, limit=1))


def _item_to_candidate_fields(
    item: dict, index: int, *, template_settings=None
) -> tuple[dict | None, str | None]:
    parsed, error = _parse_item(item, index, template_settings=template_settings)
    if error:
        return None, error
    candidate_data = {
        'title': parsed['title'],
        'proposed_domain': parsed['domain'],
        'proposed_subdomain': parsed['subdomain'],
        'proposed_topic': parsed['topic'],
        'proposed_concept': parsed['concept'],
        'proposed_knowledge_type': parsed['knowledge_type'],
        'executive_insight': parsed['executive_insight'],
        'detailed_explanation': parsed['detailed_explanation'],
        'practical_application': parsed['practical_application'],
        'consultant_use_case': parsed['consultant_use_case'],
        'course_use_case': parsed['course_use_case'],
        'common_mistakes': parsed['common_mistakes'],
        'warning_signs': parsed['warning_signs'],
        'best_practices': parsed['best_practices'],
        'example': parsed['example'],
        'keywords': parsed['keywords'],
        'citation': parsed['citation'],
        'source_quote_short': parsed['source_quote_short'],
        'reviewer_notes': parsed.get('reviewer_notes', ''),
    }
    if parsed.get('quality_warnings'):
        candidate_data['quality_warnings'] = parsed['quality_warnings']
    return candidate_data, None


def _resolve_domain_for_fast_import(parsed: dict, domain_name_raw: str) -> tuple[Domain, str]:
    """Return (domain, approval_note_fragment). Uses Uncategorized when JSON domain is missing or unmatched."""
    if parsed.get('domain'):
        return parsed['domain'], ''

    uncategorized = get_or_create_uncategorized_domain()
    if domain_name_raw:
        note = (
            f'Original domain "{domain_name_raw}" did not match taxonomy — '
            f'assigned {uncategorized.name}.'
        )
    else:
        note = f'Domain missing in JSON — assigned {uncategorized.name}.'
    return uncategorized, note


def _merge_fast_import_approval_notes(parsed: dict, domain_note: str) -> str:
    parts = []
    if domain_note:
        parts.append(domain_note)
    reviewer_notes = parsed.get('reviewer_notes', '').strip()
    if reviewer_notes:
        parts.append(reviewer_notes)
    return ' '.join(parts)


def _default_source_quality(batch: ExtractionBatch) -> str:
    if batch.source and batch.source.primary_domain_id:
        return KnowledgeUnit.ValueLevel.MEDIUM
    return KnowledgeUnit.ValueLevel.MEDIUM


def _save_batch_parse_metadata(batch: ExtractionBatch, preview: ParsePreview | FastImportPreview):
    batch.parsed_at = timezone.now()
    if preview.errors and preview.created == 0:
        batch.parse_error = '\n'.join(preview.summary_lines())
    elif preview.errors:
        batch.parse_error = '\n'.join(preview.summary_lines())
    else:
        batch.parse_error = ''
    if preview.created > 0:
        batch.status = ExtractionBatch.Status.PARSED
    batch.save(update_fields=['parsed_at', 'parse_error', 'status', 'updated_at'])


@transaction.atomic
def parse_batch_ai_output(batch: ExtractionBatch) -> ParsePreview:
    """
    Parse ai_output_raw and create ExtractionCandidate rows.
    Skips duplicate titles within the batch. Does not delete existing candidates.
    """
    preview = ParsePreview()

    try:
        items = extract_json_array(batch.ai_output_raw)
    except ValueError as exc:
        preview.errors.append(str(exc))
        batch.parsed_at = timezone.now()
        batch.parse_error = str(exc)
        batch.save(update_fields=['parsed_at', 'parse_error', 'updated_at'])
        return preview

    if not items:
        preview.errors.append('JSON array is empty — no candidates to create.')
        _save_batch_parse_metadata(batch, preview)
        return preview

    template_settings = EffectiveTemplateSettings(batch.prompt_template)

    for index, item in enumerate(items):
        fields, error = _item_to_candidate_fields(
            item, index, template_settings=template_settings
        )
        if error:
            preview.skipped_invalid += 1
            preview.errors.append(error)
            continue

        if _candidate_exists(batch, fields['title']):
            preview.skipped_duplicates += 1
            continue

        quality_warnings = fields.pop('quality_warnings', None)
        if quality_warnings:
            preview.quality_warnings += len(quality_warnings)

        ExtractionCandidate.objects.create(batch=batch, **fields)
        preview.created += 1

    _save_batch_parse_metadata(batch, preview)
    return preview


@transaction.atomic
def fast_import_batch_ai_output(batch: ExtractionBatch) -> FastImportPreview:
    """
    Parse ai_output_raw and create KnowledgeUnit rows directly (no candidates).
    Skips exact duplicate titles in the knowledge library.
    """
    preview = FastImportPreview()

    try:
        items = extract_json_array(batch.ai_output_raw)
    except ValueError as exc:
        preview.errors.append(str(exc))
        batch.parsed_at = timezone.now()
        batch.parse_error = str(exc)
        batch.save(update_fields=['parsed_at', 'parse_error', 'updated_at'])
        return preview

    if not items:
        preview.errors.append('JSON array is empty — nothing to import.')
        _save_batch_parse_metadata(batch, preview)
        return preview

    source_quality = _default_source_quality(batch)
    template_settings = EffectiveTemplateSettings(batch.prompt_template)

    for index, item in enumerate(items):
        parsed, error = _parse_item(item, index, template_settings=template_settings)
        if error:
            preview.skipped_invalid += 1
            preview.errors.append(error)
            continue

        if parsed.get('quality_warnings'):
            preview.quality_warnings += len(parsed['quality_warnings'])

        title = parsed['title']
        if _knowledge_unit_exact_exists(title):
            preview.skipped_duplicates += 1
            continue

        domain_name_raw = _normalize_str(item.get('domain'))
        domain, domain_note = _resolve_domain_for_fast_import(parsed, domain_name_raw)

        has_similar = _has_similar_knowledge_unit(title)
        if has_similar:
            preview.skipped_similar += 1

        page_ref = parsed.get('page_reference', '')[:100]

        KnowledgeUnit.objects.create(
            title=title,
            domain=domain,
            subdomain=parsed['subdomain'],
            topic=parsed['topic'],
            concept=parsed['concept'],
            source=batch.source,
            chapter=batch.chapter,
            page_reference=page_ref,
            knowledge_type=parsed['knowledge_type'] or KnowledgeUnit.KnowledgeType.OTHER,
            executive_insight=parsed['executive_insight'],
            detailed_explanation=parsed['detailed_explanation'],
            practical_application=parsed['practical_application'],
            consultant_use_case=parsed['consultant_use_case'],
            course_use_case=parsed['course_use_case'],
            common_mistakes=parsed['common_mistakes'],
            warning_signs=parsed['warning_signs'],
            best_practices=parsed['best_practices'],
            example=parsed['example'],
            keywords=parsed['keywords'],
            citation=parsed['citation'],
            source_quote_short=parsed['source_quote_short'],
            review_status=KnowledgeUnit.ReviewStatus.AI_EXTRACTED,
            governance_status=KnowledgeUnit.GovernanceStatus.PENDING_REVIEW,
            confidence_level=KnowledgeUnit.ValueLevel.MEDIUM,
            source_quality=source_quality,
            would_i_use_this=True,
            imported_from_batch=batch,
            imported_via=KnowledgeUnit.ImportedVia.FAST_IMPORT,
            approval_notes=_merge_fast_import_approval_notes(parsed, domain_note),
        )
        preview.created += 1
        if has_similar:
            preview.flagged_similar += 1

    _save_batch_parse_metadata(batch, preview)
    return preview


def bulk_fast_import_batches(batches) -> FastImportPreview:
    """Run fast import on multiple batches; aggregate preview counts."""
    aggregate = FastImportPreview()
    for batch in batches:
        if not batch.ai_output_raw.strip():
            continue
        result = fast_import_batch_ai_output(batch)
        aggregate.created += result.created
        aggregate.skipped_duplicates += result.skipped_duplicates
        aggregate.skipped_similar += result.skipped_similar
        aggregate.flagged_similar += result.flagged_similar
        aggregate.skipped_invalid += result.skipped_invalid
        aggregate.errors.extend(result.errors)
    return aggregate
