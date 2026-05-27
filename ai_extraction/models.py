from django.db import models

from config.models import TimestampedModel, UUIDModel
from knowledge.models import KnowledgeUnit
from library.models import Chapter, Source
from taxonomy.models import Concept, Domain, Subdomain, Topic


class ExtractionPromptTemplate(UUIDModel, TimestampedModel):
    class ExtractionStyle(models.TextChoices):
        GENERAL = 'general', 'General'
        CONSULTANT = 'consultant', 'Consultant'
        ACADEMIC = 'academic', 'Academic'
        COURSE_CREATION = 'course_creation', 'Course Creation'
        EXECUTIVE_SUMMARY = 'executive_summary', 'Executive Summary'
        CLAIMS_ANALYSIS = 'claims_analysis', 'Claims Analysis'
        CONTRACT_ANALYSIS = 'contract_analysis', 'Contract Analysis'
        PROJECT_CONTROLS = 'project_controls', 'Project Controls'
        OPERATIONAL_LESSONS = 'operational_lessons', 'Operational Lessons'
        CHECKLIST_GENERATION = 'checklist_generation', 'Checklist Generation'

    class TargetGranularity(models.TextChoices):
        HIGH_LEVEL = 'high_level', 'High Level'
        MEDIUM = 'medium', 'Medium'
        ATOMIC = 'atomic', 'Atomic'

    class MinimumQualityThreshold(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    source_domain = models.ForeignKey(
        Domain, on_delete=models.SET_NULL, null=True, blank=True, related_name='prompt_templates'
    )
    prompt_text = models.TextField()
    output_format_notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    extraction_style = models.CharField(
        max_length=30,
        choices=ExtractionStyle.choices,
        default=ExtractionStyle.GENERAL,
    )
    target_granularity = models.CharField(
        max_length=20,
        choices=TargetGranularity.choices,
        default=TargetGranularity.MEDIUM,
    )
    minimum_quality_threshold = models.CharField(
        max_length=10,
        choices=MinimumQualityThreshold.choices,
        default=MinimumQualityThreshold.MEDIUM,
    )
    require_page_references = models.BooleanField(default=False)
    require_source_traceability = models.BooleanField(default=False)
    require_practical_application = models.BooleanField(default=True)
    require_consultant_use_case = models.BooleanField(default=False)
    require_course_use_case = models.BooleanField(default=False)
    require_warning_signs = models.BooleanField(default=False)
    require_common_mistakes = models.BooleanField(default=False)
    require_best_practices = models.BooleanField(default=False)
    avoid_generic_filler = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ExtractionBatch(UUIDModel, TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        READY_FOR_AI = 'ready_for_ai', 'Ready for AI'
        AI_OUTPUT_RECEIVED = 'ai_output_received', 'AI Output Received'
        PARSED = 'parsed', 'Parsed'
        IMPORTED = 'imported', 'Imported'
        ARCHIVED = 'archived', 'Archived'

    source = models.ForeignKey(
        Source, on_delete=models.SET_NULL, null=True, blank=True, related_name='extraction_batches'
    )
    chapter = models.ForeignKey(
        Chapter, on_delete=models.SET_NULL, null=True, blank=True, related_name='extraction_batches'
    )
    title = models.CharField(max_length=500)
    input_text = models.TextField()
    prompt_template = models.ForeignKey(
        ExtractionPromptTemplate, on_delete=models.PROTECT, related_name='batches'
    )
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
    ai_output_raw = models.TextField(blank=True)
    parsed_at = models.DateTimeField(null=True, blank=True)
    parse_error = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name_plural = 'extraction batches'

    def __str__(self):
        return self.title

    def build_combined_prompt(self, profile_key: str | None = None):
        """Build structured prompt via prompt_builder (backward-compatible entry point)."""
        from .prompt_builder import build_prompt_for_batch

        return build_prompt_for_batch(self, profile_key=profile_key).full_prompt

    @property
    def parse_ui_state(self) -> str:
        """UI label: pending_parse | parsed_success | parse_errors | no_output."""
        if not self.ai_output_raw.strip():
            return 'no_output'
        if not self.parsed_at:
            return 'pending_parse'
        if self.parse_error.strip():
            return 'parse_errors'
        return 'parsed_success'

    def get_parse_ui_state_display(self) -> str:
        labels = {
            'no_output': 'No AI output',
            'pending_parse': 'Pending parse',
            'parsed_success': 'Parsed successfully',
            'parse_errors': 'Parse errors',
        }
        return labels.get(self.parse_ui_state, self.parse_ui_state)


class ExtractionCandidate(UUIDModel, TimestampedModel):
    class ImportStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        IMPORTED = 'imported', 'Imported'
        REJECTED = 'rejected', 'Rejected'

    batch = models.ForeignKey(ExtractionBatch, on_delete=models.CASCADE, related_name='candidates')
    title = models.CharField(max_length=500)
    proposed_domain = models.ForeignKey(
        Domain, on_delete=models.SET_NULL, null=True, blank=True, related_name='extraction_candidates'
    )
    proposed_subdomain = models.ForeignKey(
        Subdomain, on_delete=models.SET_NULL, null=True, blank=True, related_name='extraction_candidates'
    )
    proposed_topic = models.ForeignKey(
        Topic, on_delete=models.SET_NULL, null=True, blank=True, related_name='extraction_candidates'
    )
    proposed_concept = models.ForeignKey(
        Concept, on_delete=models.SET_NULL, null=True, blank=True, related_name='extraction_candidates'
    )
    proposed_knowledge_type = models.CharField(
        max_length=30, choices=KnowledgeUnit.KnowledgeType.choices, blank=True
    )
    executive_insight = models.TextField(blank=True)
    detailed_explanation = models.TextField(blank=True)
    practical_application = models.TextField(blank=True)
    consultant_use_case = models.TextField(blank=True)
    course_use_case = models.TextField(blank=True)
    common_mistakes = models.TextField(blank=True)
    warning_signs = models.TextField(blank=True)
    best_practices = models.TextField(blank=True)
    example = models.TextField(blank=True)
    keywords = models.CharField(max_length=500, blank=True)
    citation = models.TextField(blank=True)
    source_quote_short = models.TextField(blank=True)
    import_status = models.CharField(
        max_length=20, choices=ImportStatus.choices, default=ImportStatus.PENDING
    )
    imported_knowledge_unit = models.ForeignKey(
        KnowledgeUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='extraction_candidates',
    )
    reviewer_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['batch', 'title'],
                name='unique_candidate_title_per_batch',
            ),
        ]

    def __str__(self):
        return self.title

    def resolve_domain(self):
        if self.proposed_domain_id:
            return self.proposed_domain
        if self.batch.source and self.batch.source.primary_domain_id:
            return self.batch.source.primary_domain
        return None


class DocumentIngestionJob(UUIDModel, TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        EXTRACTING = 'extracting', 'Extracting'
        EXTRACTED = 'extracted', 'Extracted'
        FAILED = 'failed', 'Failed'
        ARCHIVED = 'archived', 'Archived'

    class ExtractionMethod(models.TextChoices):
        PYPDF = 'pypdf', 'PDF (pypdf)'
        MANUAL_TEXT = 'manual_text', 'Manual text'

    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name='ingestion_jobs')
    file = models.FileField(upload_to='ingestion/%Y/%m/', blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    extraction_method = models.CharField(
        max_length=20, choices=ExtractionMethod.choices, default=ExtractionMethod.PYPDF
    )
    extracted_text = models.TextField(blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'document ingestion job'

    def __str__(self):
        return f'{self.source.title} — ingestion {self.pk}'

    @property
    def is_pdf(self) -> bool:
        if not self.file:
            return False
        return self.file.name.lower().endswith('.pdf')


class TextChunk(UUIDModel, TimestampedModel):
    ingestion_job = models.ForeignKey(
        DocumentIngestionJob, on_delete=models.CASCADE, related_name='chunks'
    )
    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name='text_chunks')
    chapter = models.ForeignKey(
        Chapter, on_delete=models.SET_NULL, null=True, blank=True, related_name='text_chunks'
    )
    title = models.CharField(max_length=500)
    chunk_number = models.PositiveIntegerField()
    start_page = models.PositiveIntegerField(null=True, blank=True)
    end_page = models.PositiveIntegerField(null=True, blank=True)
    text = models.TextField()
    created_batch = models.ForeignKey(
        ExtractionBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='text_chunks',
    )

    class Meta:
        ordering = ['ingestion_job', 'chunk_number']
        unique_together = [['ingestion_job', 'chunk_number']]

    def __str__(self):
        return self.title
