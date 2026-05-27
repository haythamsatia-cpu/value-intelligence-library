from django.db import models

from config.models import TimestampedModel, UUIDModel
from taxonomy.models import Domain, Tag


class Author(UUIDModel, TimestampedModel):
    name = models.CharField(max_length=255)
    organization = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Source(UUIDModel, TimestampedModel):
    class SourceType(models.TextChoices):
        BOOK = 'book', 'Book'
        STANDARD = 'standard', 'Standard'
        PAPER = 'paper', 'Paper'
        CONTRACT = 'contract', 'Contract'
        REPORT = 'report', 'Report'
        LESSON_LEARNED = 'lesson_learned', 'Lesson Learned'
        ARTICLE = 'article', 'Article'
        GUIDE = 'guide', 'Guide'
        SPECIFICATION = 'specification', 'Specification'
        MANUAL = 'manual', 'Manual'
        OTHER = 'other', 'Other'

    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        CRITICAL = 'critical', 'Critical'

    class Status(models.TextChoices):
        NOT_STARTED = 'not_started', 'Not Started'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        ARCHIVED = 'archived', 'Archived'

    title = models.CharField(max_length=500)
    subtitle = models.CharField(max_length=500, blank=True)
    source_type = models.CharField(max_length=30, choices=SourceType.choices, default=SourceType.BOOK)
    authors = models.ManyToManyField(Author, blank=True, related_name='sources')
    year = models.PositiveIntegerField(null=True, blank=True)
    edition = models.CharField(max_length=100, blank=True)
    isbn = models.CharField(max_length=20, blank=True)
    publisher = models.CharField(max_length=255, blank=True)
    total_pages = models.PositiveIntegerField(null=True, blank=True)
    primary_domain = models.ForeignKey(
        Domain, on_delete=models.SET_NULL, null=True, blank=True, related_name='sources'
    )
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED)
    file = models.FileField(upload_to='sources/%Y/%m/', blank=True)
    source_file = models.FileField(
        upload_to='source_library/%Y/%m/',
        blank=True,
        help_text='Optional uploaded copy; original files on disk are not moved.',
    )
    original_file_path = models.CharField(
        max_length=2000,
        blank=True,
        help_text='Read-only reference to file on local disk (bulk import / scanner).',
    )
    source_file_size = models.PositiveBigIntegerField(null=True, blank=True)
    source_extension = models.CharField(max_length=20, blank=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name='sources')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-updated_at', 'title']

    def __str__(self):
        return self.title


class Chapter(UUIDModel, TimestampedModel):
    class ExtractionStatus(models.TextChoices):
        NOT_PROCESSED = 'not_processed', 'Not Processed'
        EXTRACTED = 'extracted', 'Extracted'
        REVIEWED = 'reviewed', 'Reviewed'
        APPROVED = 'approved', 'Approved'
        ARCHIVED = 'archived', 'Archived'

    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name='chapters')
    chapter_number = models.CharField(max_length=50, blank=True)
    title = models.CharField(max_length=500)
    start_page = models.PositiveIntegerField(null=True, blank=True)
    end_page = models.PositiveIntegerField(null=True, blank=True)
    extraction_status = models.CharField(
        max_length=20, choices=ExtractionStatus.choices, default=ExtractionStatus.NOT_PROCESSED
    )
    summary = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['source__title', 'chapter_number', 'title']

    def __str__(self):
        label = self.chapter_number or self.title
        return f'{self.source.title} — {label}'
