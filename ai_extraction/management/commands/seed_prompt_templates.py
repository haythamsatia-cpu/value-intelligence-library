from django.core.management.base import BaseCommand

from ai_extraction.json_instructions import JSON_OUTPUT_INSTRUCTIONS
from ai_extraction.models import ExtractionPromptTemplate
from taxonomy.models import Domain

BASE_INSTRUCTIONS = """
You are extracting atomic knowledge units from construction management source text.

Rules:
- Extract only substantive, reusable insights (not filler or paraphrase padding).
- One knowledge unit = one clear idea, principle, process, risk, or practice.
- Preserve source traceability: include short quotes and citation hints where possible.
- Do not invent page numbers or facts not present in the source text.
- Mark uncertainty explicitly when the source is ambiguous.
- Prefer concrete, consultant-ready and course-ready phrasing.
"""

TEMPLATE_SPECS = [
    {
        'name': 'General Construction Knowledge Extraction',
        'description': 'Default template for books, guides, and general construction references.',
        'domain_name': None,
        'extraction_style': 'general',
        'focus': 'Focus on broadly applicable construction management knowledge across delivery, commercial, technical, and operational themes.',
        'extra_notes': '',
    },
    {
        'name': 'Claims Management Extraction',
        'description': 'For claims, disputes, delay, and quantum content.',
        'domain_name': 'Claims Management',
        'extraction_style': 'claims_analysis',
        'focus': 'Focus on claims strategy, notices, delay analysis, quantum, prolongation, dispute avoidance, and settlement.',
        'extra_notes': 'Tag knowledge_type appropriately (risk, process, decision_rule, lesson_learned, etc.).',
    },
    {
        'name': 'Contracts Management Extraction',
        'description': 'For contract forms, administration, and commercial clauses.',
        'domain_name': 'Contracts Management',
        'extraction_style': 'contract_analysis',
        'focus': 'Focus on contract mechanisms, obligations, variations, payment, termination, and NEC/FIDIC/JCT nuances.',
        'extra_notes': 'Cite clause references when present in the source text.',
    },
    {
        'name': 'Project Controls Extraction',
        'description': 'For planning, cost, reporting, and control processes.',
        'domain_name': 'Project Controls',
        'extraction_style': 'project_controls',
        'focus': 'Focus on baselines, performance measurement, earned value, reporting, and change control.',
        'extra_notes': 'Include metrics or formulae only when stated in the source.',
    },
    {
        'name': 'Course Creation Extraction',
        'description': 'Optimize extractions for teaching and curriculum design.',
        'domain_name': 'Leadership & Management',
        'extraction_style': 'course_creation',
        'require_course_use_case': True,
        'focus': 'Emphasize course_use_case, learning progression, and clear examples for modules and assessments.',
        'extra_notes': 'Prioritize teaching-ready phrasing.',
    },
    {
        'name': 'Consultancy Insight Extraction',
        'description': 'Optimize extractions for advisory and client-facing work.',
        'domain_name': 'Commercial Management',
        'extraction_style': 'consultant',
        'require_consultant_use_case': True,
        'focus': 'Emphasize consultant_use_case, decision rules, warning signs, and practical_application.',
        'extra_notes': 'Keep executive_insight concise and action-oriented.',
    },
]


class Command(BaseCommand):
    help = 'Seed starter AI extraction prompt templates with JSON output instructions.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--update',
            action='store_true',
            help='Update existing templates with latest prompt text and JSON instructions.',
        )

    def handle(self, *args, **options):
        update = options['update']
        created = 0
        updated = 0

        for spec in TEMPLATE_SPECS:
            domain = None
            if spec['domain_name']:
                domain = Domain.objects.filter(name=spec['domain_name']).first()

            prompt_text = f'{BASE_INSTRUCTIONS.strip()}\n\n{spec["focus"]}'
            output_notes = spec['extra_notes']
            if output_notes:
                output_notes += '\n\n'
            output_notes += JSON_OUTPUT_INSTRUCTIONS.strip()

            defaults = {
                'description': spec['description'],
                'source_domain': domain,
                'prompt_text': prompt_text,
                'output_format_notes': output_notes,
                'is_active': True,
                'extraction_style': spec.get('extraction_style', 'general'),
                'require_course_use_case': spec.get('require_course_use_case', False),
                'require_consultant_use_case': spec.get('require_consultant_use_case', False),
                'require_practical_application': True,
                'require_source_traceability': True,
            }

            obj, was_created = ExtractionPromptTemplate.objects.get_or_create(
                name=spec['name'],
                defaults=defaults,
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'Created template: {spec["name"]}'))
            elif update:
                for key, value in defaults.items():
                    setattr(obj, key, value)
                obj.save()
                updated += 1
                self.stdout.write(self.style.SUCCESS(f'Updated template: {spec["name"]}'))
            else:
                self.stdout.write(f'Template exists: {spec["name"]} (use --update to refresh)')

        self.stdout.write(
            self.style.SUCCESS(f'Done. {created} created, {updated} updated.')
        )
