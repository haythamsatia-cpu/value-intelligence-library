"""
JSON output specification for Claude extraction (backward-compatible core + optional fields).
"""

CORE_JSON_KEYS = [
    'title',
    'domain',
    'subdomain',
    'topic',
    'concept',
    'knowledge_type',
    'executive_insight',
    'detailed_explanation',
    'practical_application',
    'consultant_use_case',
    'course_use_case',
    'common_mistakes',
    'warning_signs',
    'best_practices',
    'example',
    'keywords',
    'citation',
    'source_quote_short',
]

OPTIONAL_EXTENDED_JSON_KEYS = [
    'page_reference',
    'source_traceability_note',
    'operational_implication',
    'contractual_implication',
    'financial_implication',
    'schedule_implication',
    'field_application',
    'risk_if_ignored',
]


def build_json_output_spec(template_settings=None) -> str:
    """Build JSON instructions; optional fields emphasized per template flags."""
    keys = list(CORE_JSON_KEYS)
    optional = list(OPTIONAL_EXTENDED_JSON_KEYS)

    emphasize = []
    if template_settings:
        if getattr(template_settings, 'require_page_references', False):
            emphasize.extend(['page_reference', 'source_traceability_note'])
        if getattr(template_settings, 'require_source_traceability', False):
            emphasize.extend(['source_traceability_note', 'source_quote_short', 'citation'])

    key_lines = '\n'.join(f'- {k}' for k in keys)
    opt_lines = '\n'.join(f'- {k}' for k in optional)
    emph = ''
    if emphasize:
        emph = '\nStrongly include when supported by source: ' + ', '.join(sorted(set(emphasize))) + '.\n'

    return f"""
OUTPUT FORMAT (required):
Respond with ONLY a valid JSON array. No markdown fences, no commentary before or after.

Each array element must be an object with these keys (use empty string "" if unknown):

Required / core keys:
{key_lines}

Optional extended keys (include when relevant; older outputs without these still parse):
{opt_lines}
{emph}
knowledge_type values: principle, formula, process, risk, best_practice, warning_sign, methodology,
checklist, case_insight, decision_rule, example, definition, framework, lesson_learned, other

Example (abbreviated):
[
  {{
    "title": "Short specific headline",
    "domain": "Project Controls",
    "knowledge_type": "best_practice",
    "executive_insight": "...",
    "practical_application": "...",
    "page_reference": "pp. 42-43",
    "source_traceability_note": "Section 3.2 — delay notice requirements"
  }}
]
"""


# Backward compatibility for imports
JSON_OUTPUT_INSTRUCTIONS = build_json_output_spec()
