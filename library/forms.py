from django import forms

from config.forms import BootstrapFormMixin
from taxonomy.models import Domain

from .models import Author, Chapter, Source
from .source_form_helpers import assign_authors_from_text, assign_tags_from_text, authors_to_text, tags_to_text


class BulkImportCsvUploadForm(BootstrapFormMixin, forms.Form):
    csv_file = forms.FileField(label='CSV file')


class BulkFolderScanForm(BootstrapFormMixin, forms.Form):
    folder_path = forms.CharField(
        label='Root folder path',
        max_length=2000,
        widget=forms.TextInput(attrs={'placeholder': r'C:\Books\Construction Claims'}),
        help_text='Read-only scan. Original files are never moved or deleted.',
    )


class BulkImportOptionsForm(BootstrapFormMixin, forms.Form):
    default_domain = forms.ModelChoiceField(
        queryset=Domain.objects.order_by('name'),
        required=False,
        label='Default domain for rows without a match',
    )
    skip_duplicates = forms.BooleanField(initial=True, required=False, label='Skip flagged duplicates')


class AuthorForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Author
        fields = ['name', 'organization', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 4})}


class SourceForm(BootstrapFormMixin, forms.ModelForm):
    authors_text = forms.CharField(
        label='Authors',
        required=False,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Martin Barnes; John Smith',
                'class': 'form-control form-control-sm source-token-fallback',
            }
        ),
        help_text='Search existing authors or add new ones.',
    )
    tags_text = forms.CharField(
        label='Tags',
        required=False,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'contracts, nec, claims',
                'class': 'form-control form-control-sm source-token-fallback',
            }
        ),
        help_text='Search existing tags or add new ones.',
    )

    class Meta:
        model = Source
        fields = [
            'title',
            'subtitle',
            'source_type',
            'year',
            'edition',
            'isbn',
            'publisher',
            'total_pages',
            'primary_domain',
            'priority',
            'status',
            'file',
            'source_file',
            'original_file_path',
            'source_extension',
            'source_file_size',
            'notes',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Book or document title'}),
            'subtitle': forms.TextInput(attrs={'placeholder': 'Optional subtitle'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'original_file_path': forms.TextInput(
                attrs={'placeholder': r'C:\Books\Reference\my-book.pdf'}
            ),
            'source_extension': forms.TextInput(attrs={'placeholder': '.pdf'}),
            'year': forms.NumberInput(attrs={'min': 1000, 'max': 2100, 'placeholder': '2024'}),
            'edition': forms.TextInput(attrs={'placeholder': '1st'}),
            'isbn': forms.TextInput(attrs={'placeholder': '978…'}),
            'total_pages': forms.NumberInput(attrs={'min': 1, 'placeholder': '350'}),
            'source_file_size': forms.NumberInput(attrs={'min': 0, 'placeholder': 'Bytes'}),
        }
        help_texts = {
            'file': 'Legacy upload field (optional).',
            'source_file': 'Optional copy stored in the app. Original disk files are not moved.',
            'original_file_path': 'Reference to the file on your computer (bulk import / scanner).',
            'source_extension': 'e.g. .pdf, .docx — used for library badges.',
            'source_file_size': 'File size in bytes (from scanner or manual entry).',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['primary_domain'].empty_label = '—'
        for field_name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                continue
            if field_name in ('authors_text', 'tags_text'):
                continue
            if isinstance(widget, forms.Select):
                widget.attrs['class'] = 'form-select form-select-sm'
            else:
                widget.attrs['class'] = 'form-control form-control-sm'
        if self.instance and self.instance.pk:
            self.fields['authors_text'].initial = authors_to_text(self.instance)
            self.fields['tags_text'].initial = tags_to_text(self.instance)

    def save(self, commit=True):
        authors_raw = self.cleaned_data.get('authors_text', '')
        tags_raw = self.cleaned_data.get('tags_text', '')
        instance = super().save(commit=commit)
        if commit and instance.pk:
            assign_authors_from_text(instance, authors_raw)
            assign_tags_from_text(instance, tags_raw)
        return instance


class ChapterForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Chapter
        fields = [
            'source', 'chapter_number', 'title', 'start_page', 'end_page',
            'extraction_status', 'summary', 'notes',
        ]
        widgets = {
            'summary': forms.Textarea(attrs={'rows': 4}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
