from django import forms

from config.forms import BootstrapFormMixin
from taxonomy.models import Domain

from .models import Author, Chapter, Source


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
    class Meta:
        model = Source
        fields = [
            'title',
            'subtitle',
            'source_type',
            'authors',
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
            'tags',
            'notes',
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 4}),
        }


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
