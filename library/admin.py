from django.contrib import admin

from .models import Author, Chapter, Source


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'created_at', 'updated_at')
    search_fields = ('name', 'organization', 'notes')
    ordering = ('name',)


class ChapterInline(admin.TabularInline):
    model = Chapter
    extra = 0
    fields = ('chapter_number', 'title', 'start_page', 'end_page', 'extraction_status')


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'source_type',
        'source_extension',
        'year',
        'priority',
        'status',
        'primary_domain',
        'updated_at',
    )
    list_filter = ('source_type', 'priority', 'status', 'primary_domain', 'source_extension')
    search_fields = ('title', 'subtitle', 'isbn', 'publisher', 'notes', 'original_file_path')
    ordering = ('-updated_at', 'title')
    filter_horizontal = ('authors', 'tags')
    autocomplete_fields = ('primary_domain',)
    inlines = [ChapterInline]


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ('title', 'source', 'chapter_number', 'extraction_status', 'start_page', 'end_page')
    list_filter = ('extraction_status', 'source')
    search_fields = ('title', 'chapter_number', 'summary', 'notes', 'source__title')
    ordering = ('source__title', 'chapter_number')
    autocomplete_fields = ('source',)
