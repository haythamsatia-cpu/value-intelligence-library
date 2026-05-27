from config.csv_export import csv_response

from .models import KnowledgeUnit


def export_knowledge_units_csv(queryset=None):
    qs = queryset or KnowledgeUnit.objects.select_related(
        'domain', 'subdomain', 'topic', 'concept', 'source', 'chapter'
    ).prefetch_related('tags')

    header = [
        'id', 'title', 'knowledge_type', 'domain', 'subdomain', 'topic', 'concept',
        'source', 'chapter', 'page_reference', 'review_status',
        'real_world_applicability', 'consulting_value', 'teaching_value', 'difficulty_level',
        'would_i_use_this', 'tags', 'keywords', 'executive_insight', 'detailed_explanation',
        'practical_application', 'consultant_use_case', 'course_use_case',
        'common_mistakes', 'warning_signs', 'best_practices', 'example',
        'personal_commentary', 'source_quote_short', 'citation',
        'created_at', 'updated_at',
    ]
    rows = []
    for unit in qs:
        rows.append([
            str(unit.pk),
            unit.title,
            unit.knowledge_type,
            unit.domain.name,
            unit.subdomain.name if unit.subdomain else '',
            unit.topic.name if unit.topic else '',
            unit.concept.name if unit.concept else '',
            unit.source.title if unit.source else '',
            unit.chapter.title if unit.chapter else '',
            unit.page_reference,
            unit.review_status,
            unit.real_world_applicability,
            unit.consulting_value,
            unit.teaching_value,
            unit.difficulty_level,
            'yes' if unit.would_i_use_this else 'no',
            '; '.join(t.name for t in unit.tags.all()),
            unit.keywords,
            unit.executive_insight,
            unit.detailed_explanation,
            unit.practical_application,
            unit.consultant_use_case,
            unit.course_use_case,
            unit.common_mistakes,
            unit.warning_signs,
            unit.best_practices,
            unit.example,
            unit.personal_commentary,
            unit.source_quote_short,
            unit.citation,
            unit.created_at.isoformat(),
            unit.updated_at.isoformat(),
        ])
    return csv_response('knowledge_units.csv', rows, header)
