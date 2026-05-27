"""
Centralized extraction instruction blocks for prompt assembly.
Composable sections — not one giant hardcoded prompt.
"""

RULE_AVOID_FILLER = (
    'Avoid filler: no vague summaries, motivational language, or restating headings without insight.'
)

RULE_AVOID_REPETITION = (
    'Do not repeat the same idea across multiple units. Split distinct ideas into separate objects.'
)

RULE_REUSABLE_INTELLIGENCE = (
    'Prioritize reusable professional intelligence: decisions, criteria, thresholds, and field-tested practices.'
)

RULE_ATOMIC_UNITS = (
    'Extract atomic knowledge units: one principle, process, risk, formula, checklist item, or decision rule per object.'
)

RULE_NO_BUSINESS_FLUFF = (
    'Avoid generic business fluff (e.g. "communication is key", "stakeholders matter") unless tied to a specific mechanism.'
)

RULE_CONTRACT_SPECIFICITY = (
    'Preserve contractual and project-controls specificity: notice periods, entitlements, measurement rules, and defined terms.'
)

RULE_ACTIONABLE = (
    'Prefer actionable insights: what to do, when, with what evidence, and what failure looks like.'
)

RULE_SOURCE_TRACEABILITY = (
    'Preserve source traceability: short quotes, page/section references when present in the input, and clear citations.'
)

RULE_OPERATIONAL_IMPLICATIONS = (
    'State operational implications: what changes on site, in meetings, or in deliverables if this insight applies.'
)

RULE_CONSULTING_IMPLICATIONS = (
    'State consulting implications: how an advisor would use this in assessments, reports, or client workshops.'
)

RULE_FAILURE_PATTERNS = (
    'Include common failure patterns and warning signs when the source material supports them.'
)

RULE_FIELD_APPLICABILITY = (
    'Clarify field applicability: contract type, project phase, role, or context where the insight applies.'
)

RULE_PAGE_REFERENCES = (
    'When page or section markers exist in the input, include page_reference and source_traceability_note.'
)

RULE_PRACTICAL_APPLICATION = (
    'Every unit should include practical_application describing how to apply the insight in real work.'
)

RULE_CONSULTANT_USE_CASE = (
    'Include consultant_use_case: how a construction management consultant would apply this on engagements.'
)

RULE_COURSE_USE_CASE = (
    'Include course_use_case when relevant: how this would be taught or assessed in professional education.'
)

RULE_WARNING_SIGNS = (
    'Extract warning_signs when the source describes red flags, symptoms of problems, or early indicators.'
)

RULE_COMMON_MISTAKES = (
    'Extract common_mistakes when the source describes typical errors practitioners make.'
)

RULE_BEST_PRACTICES = (
    'Extract best_practices when the source describes recommended approaches or standards of care.'
)

# Registry for UI / prompt builder
ALL_RULES: dict[str, str] = {
    'avoid_filler': RULE_AVOID_FILLER,
    'avoid_repetition': RULE_AVOID_REPETITION,
    'reusable_intelligence': RULE_REUSABLE_INTELLIGENCE,
    'atomic_units': RULE_ATOMIC_UNITS,
    'no_business_fluff': RULE_NO_BUSINESS_FLUFF,
    'contract_specificity': RULE_CONTRACT_SPECIFICITY,
    'actionable': RULE_ACTIONABLE,
    'source_traceability': RULE_SOURCE_TRACEABILITY,
    'operational_implications': RULE_OPERATIONAL_IMPLICATIONS,
    'consulting_implications': RULE_CONSULTING_IMPLICATIONS,
    'failure_patterns': RULE_FAILURE_PATTERNS,
    'field_applicability': RULE_FIELD_APPLICABILITY,
    'page_references': RULE_PAGE_REFERENCES,
    'practical_application': RULE_PRACTICAL_APPLICATION,
    'consultant_use_case': RULE_CONSULTANT_USE_CASE,
    'course_use_case': RULE_COURSE_USE_CASE,
    'warning_signs': RULE_WARNING_SIGNS,
    'common_mistakes': RULE_COMMON_MISTAKES,
    'best_practices': RULE_BEST_PRACTICES,
}

STYLE_RULE_KEYS: dict[str, list[str]] = {
    'general': ['avoid_filler', 'atomic_units', 'reusable_intelligence', 'actionable'],
    'consultant': [
        'avoid_filler', 'atomic_units', 'consulting_implications', 'consultant_use_case',
        'failure_patterns', 'actionable',
    ],
    'academic': ['atomic_units', 'source_traceability', 'avoid_repetition'],
    'course_creation': ['atomic_units', 'course_use_case', 'practical_application', 'reusable_intelligence'],
    'executive_summary': ['avoid_filler', 'actionable', 'reusable_intelligence'],
    'claims_analysis': [
        'contract_specificity', 'source_traceability', 'failure_patterns', 'warning_signs',
        'consulting_implications',
    ],
    'contract_analysis': [
        'contract_specificity', 'source_traceability', 'warning_signs', 'page_references',
    ],
    'project_controls': [
        'operational_implications', 'actionable', 'failure_patterns', 'field_applicability',
    ],
    'operational_lessons': [
        'operational_implications', 'common_mistakes', 'warning_signs', 'field_applicability',
    ],
    'checklist_generation': [
        'atomic_units', 'best_practices', 'practical_application', 'actionable',
    ],
}

GRANULARITY_NOTES: dict[str, str] = {
    'high_level': 'Target high-level themes: fewer, broader units covering major ideas only.',
    'medium': 'Target medium granularity: balanced coverage of principles and supporting detail.',
    'atomic': 'Target atomic granularity: many small, single-idea units; split compound sections.',
}

QUALITY_THRESHOLD_NOTES: dict[str, str] = {
    'low': 'Accept concise extractions when the source is thin; still avoid pure filler.',
    'medium': 'Standard quality: each unit must have a clear insight and at least one application field.',
    'high': 'High quality bar: rich detail, traceability, implications, and failure patterns where supported.',
}


def rules_for_template(template) -> list[str]:
    """Collect applicable rule texts from template flags and extraction style."""
    keys: list[str] = list(STYLE_RULE_KEYS.get(template.extraction_style, STYLE_RULE_KEYS['general']))
    if template.avoid_generic_filler and 'avoid_filler' not in keys:
        keys.insert(0, 'avoid_filler')
    if template.require_page_references and 'page_references' not in keys:
        keys.append('page_references')
    if template.require_source_traceability and 'source_traceability' not in keys:
        keys.append('source_traceability')
    if template.require_practical_application and 'practical_application' not in keys:
        keys.append('practical_application')
    if template.require_consultant_use_case and 'consultant_use_case' not in keys:
        keys.append('consultant_use_case')
    if template.require_course_use_case and 'course_use_case' not in keys:
        keys.append('course_use_case')
    if template.require_warning_signs and 'warning_signs' not in keys:
        keys.append('warning_signs')
    if template.require_common_mistakes and 'common_mistakes' not in keys:
        keys.append('common_mistakes')
    if template.require_best_practices and 'best_practices' not in keys:
        keys.append('best_practices')
    extra = getattr(template, 'extra_rule_keys', None) or ()
    for key in extra:
        if key not in keys:
            keys.append(key)
    seen = set()
    rules = []
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        if key in ALL_RULES:
            rules.append(ALL_RULES[key])
    return rules
