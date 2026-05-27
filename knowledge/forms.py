from django import forms

from config.forms import BootstrapFormMixin

from .models import KnowledgeRelationship, KnowledgeUnit


class KnowledgeUnitForm(BootstrapFormMixin, forms.ModelForm):
    FIELD_SECTIONS = [
        (
            'Source & Classification',
            [
                'title', 'knowledge_type', 'domain', 'subdomain', 'topic', 'concept',
                'source', 'chapter', 'page_reference', 'tags', 'keywords', 'review_status',
            ],
        ),
        (
            'Core Insight',
            ['executive_insight', 'detailed_explanation'],
        ),
        (
            'Practical / Consulting / Course Use',
            ['practical_application', 'consultant_use_case', 'course_use_case', 'example'],
        ),
        (
            'Mistakes / Warnings / Best Practices',
            ['common_mistakes', 'warning_signs', 'best_practices'],
        ),
        (
            'Value Scoring',
            [
                'real_world_applicability', 'consulting_value', 'teaching_value',
                'difficulty_level', 'would_i_use_this',
            ],
        ),
        (
            'Governance',
            [
                'review_status',
                'governance_status',
                'confidence_level',
                'source_quality',
                'is_duplicate',
                'approval_notes',
            ],
        ),
        (
            'Source Traceability',
            ['source_quote_short', 'citation'],
        ),
        (
            'Personal Commentary',
            ['personal_commentary'],
        ),
    ]

    class Meta:
        model = KnowledgeUnit
        fields = [
            'title', 'domain', 'subdomain', 'topic', 'concept', 'source', 'chapter',
            'page_reference', 'knowledge_type', 'executive_insight', 'detailed_explanation',
            'practical_application', 'consultant_use_case', 'course_use_case',
            'common_mistakes', 'warning_signs', 'best_practices', 'example',
            'personal_commentary', 'real_world_applicability', 'consulting_value',
            'teaching_value', 'difficulty_level', 'review_status', 'governance_status',
            'confidence_level', 'source_quality', 'is_duplicate', 'approval_notes',
            'tags', 'keywords',
            'source_quote_short', 'citation', 'would_i_use_this',
        ]
        widgets = {
            'executive_insight': forms.Textarea(attrs={'rows': 3}),
            'detailed_explanation': forms.Textarea(attrs={'rows': 5}),
            'practical_application': forms.Textarea(attrs={'rows': 3}),
            'consultant_use_case': forms.Textarea(attrs={'rows': 3}),
            'course_use_case': forms.Textarea(attrs={'rows': 3}),
            'common_mistakes': forms.Textarea(attrs={'rows': 3}),
            'warning_signs': forms.Textarea(attrs={'rows': 3}),
            'best_practices': forms.Textarea(attrs={'rows': 3}),
            'example': forms.Textarea(attrs={'rows': 3}),
            'personal_commentary': forms.Textarea(attrs={'rows': 3}),
            'source_quote_short': forms.Textarea(attrs={'rows': 2}),
            'citation': forms.Textarea(attrs={'rows': 2}),
            'approval_notes': forms.Textarea(attrs={'rows': 2}),
        }


class KnowledgeRelationshipForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = KnowledgeRelationship
        fields = ['from_knowledge_unit', 'to_knowledge_unit', 'relationship_type', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 3})}
