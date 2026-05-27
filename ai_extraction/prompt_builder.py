"""
Dynamic prompt assembly from templates, quality profiles, source/chunk metadata, and rules.
"""
from dataclasses import dataclass, field

from .extraction_rules import GRANULARITY_NOTES, QUALITY_THRESHOLD_NOTES, rules_for_template
from .json_schema import build_json_output_spec
from .quality_profiles import EffectiveTemplateSettings, QUALITY_PROFILES


@dataclass
class BuiltPrompt:
    full_prompt: str
    applied_rules: list[str] = field(default_factory=list)
    json_schema: str = ''
    source_context: str = ''
    profile_name: str | None = None
    behavior_summary: str = ''


def _source_context_block(source, chapter=None, chunk=None) -> str:
    lines = []
    if source:
        lines.append(f'Source title: {source.title}')
        lines.append(f'Source type: {source.get_source_type_display()}')
        if source.primary_domain:
            lines.append(f'Primary domain: {source.primary_domain.name}')
        if source.year:
            lines.append(f'Year: {source.year}')
        authors = ', '.join(a.name for a in source.authors.all()[:5])
        if authors:
            lines.append(f'Authors: {authors}')
    if chapter:
        lines.append(f'Chapter: {chapter.chapter_number} {chapter.title}'.strip())
        if chapter.start_page:
            lines.append(f'Chapter pages: {chapter.start_page}-{chapter.end_page or "?"}')
    if chunk:
        lines.append(f'Chunk: {chunk.title} (#{chunk.chunk_number})')
        if chunk.start_page:
            lines.append(f'Chunk pages: {chunk.start_page}-{chunk.end_page or "?"}')
    if not lines:
        return ''
    return '--- Source context (use to tailor extraction) ---\n' + '\n'.join(lines)


def _behavior_summary(settings: EffectiveTemplateSettings) -> str:
    from .models import ExtractionPromptTemplate

    style_label = dict(ExtractionPromptTemplate.ExtractionStyle.choices).get(
        settings.extraction_style, settings.extraction_style
    )
    gran = GRANULARITY_NOTES.get(settings.target_granularity, '')
    qual = QUALITY_THRESHOLD_NOTES.get(settings.minimum_quality_threshold, '')
    parts = [
        f'Extraction style: {style_label}',
        f'Granularity: {gran}',
        f'Quality threshold: {qual}',
    ]
    if settings.profile_label:
        parts.insert(0, f'Quality profile: {settings.profile_label}')
    return '\n'.join(parts)


def build_prompt(
    template,
    input_text: str,
    *,
    source=None,
    chapter=None,
    chunk=None,
    profile_key: str | None = None,
) -> BuiltPrompt:
    """
    Assemble the full prompt for manual Claude use.
    `template` is an ExtractionPromptTemplate instance.
    """
    settings = EffectiveTemplateSettings(template, profile_key=profile_key)
    applied_rules = rules_for_template(settings)
    if settings.extra_rule_keys:
        from .extraction_rules import ALL_RULES

        for key in settings.extra_rule_keys:
            if key in ALL_RULES and ALL_RULES[key] not in applied_rules:
                applied_rules.append(ALL_RULES[key])

    source_ctx = _source_context_block(source, chapter=chapter, chunk=chunk)
    json_schema = build_json_output_spec(settings)
    behavior = _behavior_summary(settings)

    parts = []
    if behavior:
        parts.append('--- Extraction behavior ---\n' + behavior)
    if source_ctx:
        parts.append(source_ctx)
    parts.append('--- Core instructions ---\n' + settings.prompt_text.strip())
    if applied_rules:
        parts.append('--- Extraction quality rules ---\n' + '\n'.join(f'- {r}' for r in applied_rules))
    if settings.output_format_notes:
        parts.append('--- Template output notes ---\n' + settings.output_format_notes.strip())
    parts.append(json_schema.strip())
    parts.append('--- Source text to extract from ---\n' + input_text.strip())

    return BuiltPrompt(
        full_prompt='\n\n'.join(parts),
        applied_rules=applied_rules,
        json_schema=json_schema.strip(),
        source_context=source_ctx,
        profile_name=settings.profile_label,
        behavior_summary=behavior,
    )


def build_prompt_for_batch(batch, profile_key: str | None = None) -> BuiltPrompt:
    chunk = batch.text_chunks.first() if hasattr(batch, 'text_chunks') else None
    return build_prompt(
        batch.prompt_template,
        batch.input_text,
        source=batch.source,
        chapter=batch.chapter,
        chunk=chunk,
        profile_key=profile_key,
    )
