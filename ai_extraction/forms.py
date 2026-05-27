from django import forms

from config.forms import BootstrapFormMixin
from library.models import Source

from .models import (
    DocumentIngestionJob,
    ExtractionBatch,
    ExtractionCandidate,
    ExtractionPromptTemplate,
)
from .quality_profiles import PROFILE_CHOICES


class ExtractionPromptTemplateForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ExtractionPromptTemplate
        fields = [
            'name',
            'description',
            'source_domain',
            'prompt_text',
            'output_format_notes',
            'is_active',
            'extraction_style',
            'target_granularity',
            'minimum_quality_threshold',
            'require_page_references',
            'require_source_traceability',
            'require_practical_application',
            'require_consultant_use_case',
            'require_course_use_case',
            'require_warning_signs',
            'require_common_mistakes',
            'require_best_practices',
            'avoid_generic_filler',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
            'prompt_text': forms.Textarea(attrs={'rows': 12}),
            'output_format_notes': forms.Textarea(attrs={'rows': 4}),
        }


class PromptSandboxForm(BootstrapFormMixin, forms.Form):
    prompt_template = forms.ModelChoiceField(
        queryset=ExtractionPromptTemplate.objects.filter(is_active=True).order_by('name'),
        label='Prompt template',
    )
    quality_profile = forms.ChoiceField(
        required=False,
        label='Quality profile (optional)',
        choices=[('', '— Use template settings only —')] + list(PROFILE_CHOICES),
    )
    sample_text = forms.CharField(
        label='Sample source text',
        widget=forms.Textarea(attrs={'rows': 14}),
    )
    source = forms.ModelChoiceField(
        queryset=Source.objects.order_by('title'),
        required=False,
        label='Source context (optional)',
    )


class ExtractionBatchForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ExtractionBatch
        fields = ['title', 'source', 'chapter', 'prompt_template', 'input_text', 'notes']
        widgets = {
            'input_text': forms.Textarea(attrs={'rows': 14}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class ExtractionBatchAiOutputForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ExtractionBatch
        fields = ['status', 'ai_output_raw']
        widgets = {
            'ai_output_raw': forms.Textarea(attrs={'rows': 16}),
        }


class ExtractionCandidateForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ExtractionCandidate
        fields = [
            'batch', 'title', 'proposed_domain', 'proposed_subdomain', 'proposed_topic',
            'proposed_concept', 'proposed_knowledge_type', 'executive_insight',
            'detailed_explanation', 'practical_application', 'consultant_use_case',
            'course_use_case', 'common_mistakes', 'warning_signs', 'best_practices',
            'example', 'keywords', 'citation', 'source_quote_short', 'reviewer_notes',
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
            'source_quote_short': forms.Textarea(attrs={'rows': 2}),
            'citation': forms.Textarea(attrs={'rows': 2}),
            'reviewer_notes': forms.Textarea(attrs={'rows': 2}),
        }


class DocumentIngestionJobForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = DocumentIngestionJob
        fields = ['source', 'file', 'extraction_method']
        widgets = {
            'extraction_method': forms.Select(),
        }

    def clean(self):
        cleaned = super().clean()
        method = cleaned.get('extraction_method')
        file = cleaned.get('file')
        if method == DocumentIngestionJob.ExtractionMethod.PYPDF:
            if not file and not (self.instance and self.instance.file):
                raise forms.ValidationError(
                    {'file': 'A PDF file is required for PDF (pypdf) extraction.'}
                )
            check_file = file or (self.instance.file if self.instance else None)
            if check_file and not check_file.name.lower().endswith('.pdf'):
                raise forms.ValidationError(
                    {'file': 'Only PDF files are supported for PDF (pypdf) extraction.'}
                )
        return cleaned


class IngestionManualTextForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = DocumentIngestionJob
        fields = ['extracted_text']
        widgets = {
            'extracted_text': forms.Textarea(attrs={'rows': 16}),
        }


class PromptTemplateSelectForm(BootstrapFormMixin, forms.Form):
    prompt_template = forms.ModelChoiceField(
        queryset=ExtractionPromptTemplate.objects.filter(is_active=True).order_by('name'),
        label='Prompt template',
    )
