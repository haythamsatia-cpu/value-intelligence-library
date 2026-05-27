from django.contrib import admin

from .models import (
    DocumentIngestionJob,
    ExtractionBatch,
    ExtractionCandidate,
    ExtractionPromptTemplate,
    TextChunk,
)


@admin.register(ExtractionPromptTemplate)
class ExtractionPromptTemplateAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'extraction_style',
        'target_granularity',
        'minimum_quality_threshold',
        'source_domain',
        'is_active',
        'updated_at',
    )
    list_filter = (
        'is_active',
        'extraction_style',
        'target_granularity',
        'minimum_quality_threshold',
        'source_domain',
    )
    search_fields = ('name', 'description', 'prompt_text')
    ordering = ('name',)
    autocomplete_fields = ('source_domain',)
    fieldsets = (
        (None, {'fields': ('name', 'description', 'source_domain', 'is_active')}),
        ('Prompt body', {'fields': ('prompt_text', 'output_format_notes')}),
        (
            'Extraction standards',
            {
                'fields': (
                    'extraction_style',
                    'target_granularity',
                    'minimum_quality_threshold',
                    'avoid_generic_filler',
                )
            },
        ),
        (
            'Required fields',
            {
                'fields': (
                    'require_page_references',
                    'require_source_traceability',
                    'require_practical_application',
                    'require_consultant_use_case',
                    'require_course_use_case',
                    'require_warning_signs',
                    'require_common_mistakes',
                    'require_best_practices',
                )
            },
        ),
    )


class ExtractionCandidateInline(admin.TabularInline):
    model = ExtractionCandidate
    extra = 0
    fields = ('title', 'import_status', 'proposed_domain', 'proposed_knowledge_type')
    readonly_fields = ('imported_knowledge_unit',)
    show_change_link = True


@admin.register(ExtractionBatch)
class ExtractionBatchAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'parsed_at', 'prompt_template', 'source', 'chapter', 'updated_at')
    readonly_fields = ('parsed_at',)
    list_filter = ('status', 'prompt_template', 'source')
    search_fields = ('title', 'input_text', 'ai_output_raw', 'notes')
    ordering = ('-updated_at',)
    autocomplete_fields = ('source', 'chapter', 'prompt_template')
    inlines = [ExtractionCandidateInline]


@admin.register(ExtractionCandidate)
class ExtractionCandidateAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'batch', 'import_status', 'proposed_domain', 'proposed_knowledge_type', 'updated_at'
    )
    list_filter = ('import_status', 'proposed_knowledge_type', 'batch__status')
    search_fields = ('title', 'executive_insight', 'keywords', 'reviewer_notes')
    ordering = ('-created_at',)
    autocomplete_fields = (
        'batch', 'proposed_domain', 'proposed_subdomain', 'proposed_topic',
        'proposed_concept', 'imported_knowledge_unit',
    )


class TextChunkInline(admin.TabularInline):
    model = TextChunk
    extra = 0
    fields = ('chunk_number', 'title', 'start_page', 'end_page', 'created_batch')
    readonly_fields = ('created_batch',)
    show_change_link = True


@admin.register(DocumentIngestionJob)
class DocumentIngestionJobAdmin(admin.ModelAdmin):
    list_display = ('source', 'status', 'extraction_method', 'updated_at')
    list_filter = ('status', 'extraction_method')
    search_fields = ('source__title', 'extracted_text', 'error_message')
    ordering = ('-updated_at',)
    autocomplete_fields = ('source',)
    inlines = [TextChunkInline]


@admin.register(TextChunk)
class TextChunkAdmin(admin.ModelAdmin):
    list_display = ('title', 'chunk_number', 'ingestion_job', 'start_page', 'end_page', 'created_batch')
    list_filter = ('ingestion_job',)
    search_fields = ('title', 'text')
    ordering = ('ingestion_job', 'chunk_number')
    autocomplete_fields = ('ingestion_job', 'source', 'chapter', 'created_batch')
