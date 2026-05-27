from django.contrib import admin

from .models import KnowledgeRelationship, KnowledgeUnit


@admin.action(description='Mark selected as governance approved')
def mark_governance_approved(modeladmin, request, queryset):
    queryset.update(
        governance_status=KnowledgeUnit.GovernanceStatus.APPROVED,
        review_status=KnowledgeUnit.ReviewStatus.APPROVED,
    )


@admin.action(description='Mark selected as duplicates')
def mark_as_duplicates(modeladmin, request, queryset):
    queryset.update(is_duplicate=True)


@admin.action(description='Clear duplicate flag')
def clear_duplicates(modeladmin, request, queryset):
    queryset.update(is_duplicate=False, duplicate_group=None)


@admin.register(KnowledgeUnit)
class KnowledgeUnitAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'knowledge_type',
        'domain',
        'review_status',
        'governance_status',
        'confidence_level',
        'source_quality',
        'is_duplicate',
        'reviewed_by',
        'reviewed_at',
        'consulting_value',
        'teaching_value',
        'difficulty_level',
        'would_i_use_this',
        'imported_via',
        'updated_at',
    )
    list_filter = (
        'knowledge_type',
        'review_status',
        'governance_status',
        'domain',
        'consulting_value',
        'teaching_value',
        'confidence_level',
        'source_quality',
        'is_duplicate',
        'difficulty_level',
        'real_world_applicability',
        'would_i_use_this',
        'reviewed_by',
        'imported_via',
    )
    search_fields = (
        'title',
        'executive_insight',
        'detailed_explanation',
        'keywords',
        'citation',
        'personal_commentary',
        'approval_notes',
    )
    ordering = ('-updated_at', 'title')
    actions = [mark_governance_approved, mark_as_duplicates, clear_duplicates]
    filter_horizontal = ('tags',)
    autocomplete_fields = ('domain', 'subdomain', 'topic', 'concept', 'source', 'chapter', 'reviewed_by')
    fieldsets = (
        (None, {'fields': ('title', 'knowledge_type', 'review_status', 'would_i_use_this')}),
        (
            'Governance',
            {
                'fields': (
                    'governance_status',
                    'confidence_level',
                    'source_quality',
                    'is_duplicate',
                    'duplicate_group',
                    'reviewed_by',
                    'reviewed_at',
                    'approval_notes',
                )
            },
        ),
        ('Taxonomy', {'fields': ('domain', 'subdomain', 'topic', 'concept', 'tags')}),
        (
            'Import provenance',
            {'fields': ('imported_via', 'imported_from_batch')},
        ),
        ('Source reference', {'fields': ('source', 'chapter', 'page_reference', 'source_quote_short', 'citation')}),
        ('Content', {
            'fields': (
                'executive_insight',
                'detailed_explanation',
                'practical_application',
                'consultant_use_case',
                'course_use_case',
            )
        }),
        ('Guidance', {
            'fields': (
                'common_mistakes',
                'warning_signs',
                'best_practices',
                'example',
                'personal_commentary',
            )
        }),
        ('Ratings', {
            'fields': (
                'real_world_applicability',
                'consulting_value',
                'teaching_value',
                'difficulty_level',
                'keywords',
            )
        }),
    )


@admin.register(KnowledgeRelationship)
class KnowledgeRelationshipAdmin(admin.ModelAdmin):
    list_display = ('from_knowledge_unit', 'relationship_type', 'to_knowledge_unit', 'created_at')
    list_filter = ('relationship_type',)
    search_fields = (
        'from_knowledge_unit__title',
        'to_knowledge_unit__title',
        'notes',
    )
    ordering = ('-created_at',)
    autocomplete_fields = ('from_knowledge_unit', 'to_knowledge_unit')
