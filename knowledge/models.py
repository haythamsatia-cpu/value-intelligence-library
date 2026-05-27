import uuid

from django.conf import settings
from django.db import models

from config.models import TimestampedModel, UUIDModel
from library.models import Chapter, Source
from taxonomy.models import Concept, Domain, Subdomain, Tag, Topic


class KnowledgeUnit(UUIDModel, TimestampedModel):
    class KnowledgeType(models.TextChoices):
        PRINCIPLE = 'principle', 'Principle'
        FORMULA = 'formula', 'Formula'
        PROCESS = 'process', 'Process'
        RISK = 'risk', 'Risk'
        BEST_PRACTICE = 'best_practice', 'Best Practice'
        WARNING_SIGN = 'warning_sign', 'Warning Sign'
        METHODOLOGY = 'methodology', 'Methodology'
        CHECKLIST = 'checklist', 'Checklist'
        CASE_INSIGHT = 'case_insight', 'Case Insight'
        DECISION_RULE = 'decision_rule', 'Decision Rule'
        EXAMPLE = 'example', 'Example'
        DEFINITION = 'definition', 'Definition'
        FRAMEWORK = 'framework', 'Framework'
        LESSON_LEARNED = 'lesson_learned', 'Lesson Learned'
        OTHER = 'other', 'Other'

    class ValueLevel(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'

    class DifficultyLevel(models.TextChoices):
        BEGINNER = 'beginner', 'Beginner'
        INTERMEDIATE = 'intermediate', 'Intermediate'
        ADVANCED = 'advanced', 'Advanced'
        EXPERT = 'expert', 'Expert'

    class ReviewStatus(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        AI_EXTRACTED = 'ai_extracted', 'AI Extracted'
        REVIEWED = 'reviewed', 'Reviewed'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        ARCHIVED = 'archived', 'Archived'

    class GovernanceStatus(models.TextChoices):
        PENDING_REVIEW = 'pending_review', 'Pending Review'
        REVIEWED = 'reviewed', 'Reviewed'
        APPROVED = 'approved', 'Approved'
        ARCHIVED = 'archived', 'Archived'

    class ImportedVia(models.TextChoices):
        CANDIDATE_REVIEW = 'candidate_review', 'Candidate Review'
        FAST_IMPORT = 'fast_import', 'Fast Import'

    title = models.CharField(max_length=500)
    domain = models.ForeignKey(Domain, on_delete=models.PROTECT, related_name='knowledge_units')
    subdomain = models.ForeignKey(
        Subdomain, on_delete=models.SET_NULL, null=True, blank=True, related_name='knowledge_units'
    )
    topic = models.ForeignKey(
        Topic, on_delete=models.SET_NULL, null=True, blank=True, related_name='knowledge_units'
    )
    concept = models.ForeignKey(
        Concept, on_delete=models.SET_NULL, null=True, blank=True, related_name='knowledge_units'
    )
    source = models.ForeignKey(
        Source, on_delete=models.SET_NULL, null=True, blank=True, related_name='knowledge_units'
    )
    chapter = models.ForeignKey(
        Chapter, on_delete=models.SET_NULL, null=True, blank=True, related_name='knowledge_units'
    )
    page_reference = models.CharField(max_length=100, blank=True)
    knowledge_type = models.CharField(
        max_length=30, choices=KnowledgeType.choices, default=KnowledgeType.OTHER
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
    personal_commentary = models.TextField(blank=True)
    real_world_applicability = models.CharField(
        max_length=10, choices=ValueLevel.choices, default=ValueLevel.MEDIUM
    )
    consulting_value = models.CharField(
        max_length=10, choices=ValueLevel.choices, default=ValueLevel.MEDIUM
    )
    teaching_value = models.CharField(
        max_length=10, choices=ValueLevel.choices, default=ValueLevel.MEDIUM
    )
    difficulty_level = models.CharField(
        max_length=20, choices=DifficultyLevel.choices, default=DifficultyLevel.INTERMEDIATE
    )
    review_status = models.CharField(
        max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.DRAFT
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_knowledge_units',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)
    confidence_level = models.CharField(
        max_length=10, choices=ValueLevel.choices, default=ValueLevel.MEDIUM
    )
    source_quality = models.CharField(
        max_length=10, choices=ValueLevel.choices, default=ValueLevel.MEDIUM
    )
    duplicate_group = models.UUIDField(null=True, blank=True)
    is_duplicate = models.BooleanField(default=False)
    governance_status = models.CharField(
        max_length=20,
        choices=GovernanceStatus.choices,
        default=GovernanceStatus.PENDING_REVIEW,
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name='knowledge_units')
    keywords = models.CharField(max_length=500, blank=True, help_text='Comma-separated keywords')
    source_quote_short = models.TextField(blank=True)
    citation = models.TextField(blank=True)
    would_i_use_this = models.BooleanField(default=False)
    imported_from_batch = models.ForeignKey(
        'ai_extraction.ExtractionBatch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='imported_knowledge_units',
    )
    imported_via = models.CharField(
        max_length=30,
        choices=ImportedVia.choices,
        blank=True,
    )

    class Meta:
        ordering = ['-updated_at', 'title']
        verbose_name = 'Knowledge Unit'
        verbose_name_plural = 'Knowledge Units'

    def __str__(self):
        return self.title

    def assign_duplicate_group(self):
        if not self.duplicate_group:
            self.duplicate_group = uuid.uuid4()


class KnowledgeRelationship(UUIDModel, TimestampedModel):
    class RelationshipType(models.TextChoices):
        RELATED_TO = 'related_to', 'Related To'
        SUPPORTS = 'supports', 'Supports'
        CONTRADICTS = 'contradicts', 'Contradicts'
        EXAMPLE_OF = 'example_of', 'Example Of'
        PREREQUISITE_OF = 'prerequisite_of', 'Prerequisite Of'
        EXPANDS_ON = 'expands_on', 'Expands On'
        RISK_OF = 'risk_of', 'Risk Of'

    from_knowledge_unit = models.ForeignKey(
        KnowledgeUnit, on_delete=models.CASCADE, related_name='outgoing_relationships'
    )
    to_knowledge_unit = models.ForeignKey(
        KnowledgeUnit, on_delete=models.CASCADE, related_name='incoming_relationships'
    )
    relationship_type = models.CharField(max_length=30, choices=RelationshipType.choices)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Knowledge Relationship'
        verbose_name_plural = 'Knowledge Relationships'

    def __str__(self):
        return f'{self.from_knowledge_unit} → {self.relationship_type} → {self.to_knowledge_unit}'
