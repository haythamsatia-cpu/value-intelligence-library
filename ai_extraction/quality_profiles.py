"""
Predefined prompt quality profiles — overlay template settings for prompt building.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class QualityProfile:
    key: str
    label: str
    description: str
    extraction_style: str
    target_granularity: str
    minimum_quality_threshold: str
    require_page_references: bool
    require_source_traceability: bool
    require_practical_application: bool
    require_consultant_use_case: bool
    require_course_use_case: bool
    require_warning_signs: bool
    require_common_mistakes: bool
    require_best_practices: bool
    avoid_generic_filler: bool
    extra_rule_keys: tuple[str, ...] = ()


QUALITY_PROFILES: dict[str, QualityProfile] = {
    'fast_capture': QualityProfile(
        key='fast_capture',
        label='Fast Capture',
        description='Minimal bar for speed; atomic units with core insight only.',
        extraction_style='general',
        target_granularity='medium',
        minimum_quality_threshold='low',
        require_page_references=False,
        require_source_traceability=False,
        require_practical_application=True,
        require_consultant_use_case=False,
        require_course_use_case=False,
        require_warning_signs=False,
        require_common_mistakes=False,
        require_best_practices=False,
        avoid_generic_filler=True,
        extra_rule_keys=('atomic_units', 'avoid_filler'),
    ),
    'balanced': QualityProfile(
        key='balanced',
        label='Balanced',
        description='Default professional extraction with traceability and applications.',
        extraction_style='consultant',
        target_granularity='medium',
        minimum_quality_threshold='medium',
        require_page_references=True,
        require_source_traceability=True,
        require_practical_application=True,
        require_consultant_use_case=True,
        require_course_use_case=False,
        require_warning_signs=True,
        require_common_mistakes=True,
        require_best_practices=True,
        avoid_generic_filler=True,
    ),
    'consultant_grade': QualityProfile(
        key='consultant_grade',
        label='Consultant Grade',
        description='High bar for advisory-ready intelligence with implications and failures.',
        extraction_style='consultant',
        target_granularity='atomic',
        minimum_quality_threshold='high',
        require_page_references=True,
        require_source_traceability=True,
        require_practical_application=True,
        require_consultant_use_case=True,
        require_course_use_case=False,
        require_warning_signs=True,
        require_common_mistakes=True,
        require_best_practices=True,
        avoid_generic_filler=True,
        extra_rule_keys=('consulting_implications', 'operational_implications', 'failure_patterns'),
    ),
    'course_creation': QualityProfile(
        key='course_creation',
        label='Course Creation',
        description='Optimized for teaching: course use cases and clear explanations.',
        extraction_style='course_creation',
        target_granularity='medium',
        minimum_quality_threshold='medium',
        require_page_references=True,
        require_source_traceability=True,
        require_practical_application=True,
        require_consultant_use_case=False,
        require_course_use_case=True,
        require_warning_signs=True,
        require_common_mistakes=True,
        require_best_practices=True,
        avoid_generic_filler=True,
    ),
    'deep_technical': QualityProfile(
        key='deep_technical',
        label='Deep Technical Analysis',
        description='Atomic, high-detail units for contracts, claims, and controls.',
        extraction_style='contract_analysis',
        target_granularity='atomic',
        minimum_quality_threshold='high',
        require_page_references=True,
        require_source_traceability=True,
        require_practical_application=True,
        require_consultant_use_case=True,
        require_course_use_case=False,
        require_warning_signs=True,
        require_common_mistakes=True,
        require_best_practices=True,
        avoid_generic_filler=True,
        extra_rule_keys=('contract_specificity', 'field_applicability'),
    ),
}

PROFILE_CHOICES = [(p.key, p.label) for p in QUALITY_PROFILES.values()]


class EffectiveTemplateSettings:
    """Template settings with optional quality profile overlay."""

    def __init__(self, template, profile_key: str | None = None):
        self._template = template
        profile = QUALITY_PROFILES.get(profile_key) if profile_key else None
        self.profile_key = profile_key
        self.profile_label = profile.label if profile else None

        def _get(attr, default=None):
            if profile and hasattr(profile, attr):
                return getattr(profile, attr)
            return getattr(template, attr, default)

        self.extraction_style = _get('extraction_style', 'general')
        self.target_granularity = _get('target_granularity', 'medium')
        self.minimum_quality_threshold = _get('minimum_quality_threshold', 'medium')
        self.require_page_references = _get('require_page_references', False)
        self.require_source_traceability = _get('require_source_traceability', False)
        self.require_practical_application = _get('require_practical_application', False)
        self.require_consultant_use_case = _get('require_consultant_use_case', False)
        self.require_course_use_case = _get('require_course_use_case', False)
        self.require_warning_signs = _get('require_warning_signs', False)
        self.require_common_mistakes = _get('require_common_mistakes', False)
        self.require_best_practices = _get('require_best_practices', False)
        self.avoid_generic_filler = _get('avoid_generic_filler', True)
        self.extra_rule_keys = profile.extra_rule_keys if profile else ()

    @property
    def prompt_text(self):
        return self._template.prompt_text

    @property
    def output_format_notes(self):
        return self._template.output_format_notes

    @property
    def name(self):
        return self._template.name
