import json

from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from ai_extraction.models import DocumentIngestionJob, ExtractionBatch
from taxonomy.models import Domain, Tag

from .exports import export_chapters_csv, export_processing_center_csv, export_sources_csv
from .forms import AuthorForm, ChapterForm, SourceForm
from .models import Author, Chapter, Source
from .source_readiness import annotate_sources_readiness, get_source_readiness
from .processing import (
    PIPELINE_LABELS,
    PROCESSING_STATUS_CHOICES,
    QUICK_MODES,
    apply_processing_center_filters,
    bulk_source_processing_stats,
    filter_sources_by_processing,
    get_global_processing_metrics,
    get_recent_activity,
    get_source_detail_processing,
    get_source_failures,
)


class SourceListView(ListView):
    model = Source
    template_name = 'library/source_list.html'
    context_object_name = 'sources'
    paginate_by = 50

    def get_queryset(self):
        qs = Source.objects.select_related('primary_domain').prefetch_related(
            'authors', 'tags', 'ingestion_jobs', 'knowledge_units'
        )
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(title__icontains=q)
        ext = self.request.GET.get('extension', '').strip()
        if ext:
            qs = qs.filter(source_extension__iexact=ext)
        status = self.request.GET.get('status', '').strip()
        if status in dict(Source.Status.choices):
            qs = qs.filter(status=status)
        domain_id = self.request.GET.get('domain', '').strip()
        if domain_id:
            qs = qs.filter(primary_domain_id=domain_id)
        return qs

    def get_template_names(self):
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        annotate_sources_readiness(context['sources'])
        context['domains'] = Domain.objects.order_by('name')
        context['statuses'] = Source.Status.choices
        context['priorities'] = Source.Priority.choices
        context['query'] = self.request.GET.get('q', '')
        context['filter_status'] = self.request.GET.get('status', '')
        context['filter_domain'] = self.request.GET.get('domain', '')
        context['filter_extension'] = self.request.GET.get('extension', '')
        context['view_mode'] = self.request.GET.get('view', 'standard')
        return context


class SourceDetailView(DetailView):
    model = Source
    template_name = 'library/source_detail.html'
    context_object_name = 'source'

    def get_queryset(self):
        return Source.objects.select_related('primary_domain').prefetch_related(
            'authors', 'chapters', 'ingestion_jobs'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        source = self.object
        processing = get_source_detail_processing(source.pk)
        failed_jobs, failed_batches = get_source_failures(source.pk)
        context['processing'] = processing.to_dict()
        context['processing_pipeline'] = processing.pipeline
        context['failed_ingestion_jobs'] = failed_jobs
        context['failed_batches'] = failed_batches
        context['recent_activity'] = get_recent_activity(limit=12, source_id=source.pk)
        context['recent_knowledge'] = (
            source.knowledge_units.select_related('domain')
            .order_by('-created_at')[:8]
        )
        context['readiness'] = get_source_readiness(source)
        return context


class SourceFormContextMixin:
    """Token-picker option lists for source create/edit."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        authors = list(Author.objects.order_by('name').values_list('name', flat=True)[:1000])
        tags = list(Tag.objects.order_by('name').values_list('name', flat=True)[:1000])
        obj = getattr(self, 'object', None)
        if obj and obj.pk:
            for name in obj.authors.order_by('name').values_list('name', flat=True):
                if name not in authors:
                    authors.append(name)
            for name in obj.tags.order_by('name').values_list('name', flat=True):
                if name not in tags:
                    tags.append(name)
        context['author_suggestions'] = authors
        context['tag_suggestions'] = tags
        return context


class SourceCreateView(SourceFormContextMixin, CreateView):
    model = Source
    form_class = SourceForm
    template_name = 'library/source_form.html'
    success_url = reverse_lazy('library:source_list')


class SourceUpdateView(SourceFormContextMixin, UpdateView):
    model = Source
    form_class = SourceForm
    template_name = 'library/source_form.html'
    context_object_name = 'source'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object'] = self.object
        return context

    def get_success_url(self):
        return reverse_lazy('library:source_detail', kwargs={'pk': self.object.pk})


class SourceDeleteView(DeleteView):
    model = Source
    template_name = 'library/source_confirm_delete.html'
    context_object_name = 'source'
    success_url = reverse_lazy('library:source_list')


class SourceExportCSVView(View):
    def get(self, request):
        return export_sources_csv()


class ChapterListView(ListView):
    model = Chapter
    template_name = 'library/chapter_list.html'
    context_object_name = 'chapters'
    paginate_by = 25

    def get_queryset(self):
        qs = Chapter.objects.select_related('source').order_by('source__title', 'chapter_number')
        source_id = self.request.GET.get('source')
        if source_id:
            qs = qs.filter(source_id=source_id)
        status = self.request.GET.get('extraction_status')
        if status:
            qs = qs.filter(extraction_status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['sources'] = Source.objects.order_by('title')
        context['filter_source'] = self.request.GET.get('source', '')
        context['filter_status'] = self.request.GET.get('extraction_status', '')
        context['extraction_statuses'] = Chapter.ExtractionStatus.choices
        return context


class ChapterDetailView(DetailView):
    model = Chapter
    template_name = 'library/chapter_detail.html'
    context_object_name = 'chapter'

    def get_queryset(self):
        return Chapter.objects.select_related('source')


class ChapterCreateView(CreateView):
    model = Chapter
    form_class = ChapterForm
    template_name = 'library/chapter_form.html'
    success_url = reverse_lazy('library:chapter_list')

    def get_initial(self):
        initial = super().get_initial()
        source_id = self.request.GET.get('source')
        if source_id:
            initial['source'] = source_id
        return initial


class ChapterUpdateView(UpdateView):
    model = Chapter
    form_class = ChapterForm
    template_name = 'library/chapter_form.html'
    context_object_name = 'chapter'

    def get_success_url(self):
        return reverse_lazy('library:chapter_detail', kwargs={'pk': self.object.pk})


class ChapterDeleteView(DeleteView):
    model = Chapter
    template_name = 'library/chapter_confirm_delete.html'
    context_object_name = 'chapter'
    success_url = reverse_lazy('library:chapter_list')


class ChapterExportCSVView(View):
    def get(self, request):
        return export_chapters_csv(
            source_id=request.GET.get('source') or None,
            extraction_status=request.GET.get('extraction_status') or None,
        )


class AuthorListView(ListView):
    model = Author
    template_name = 'library/author_list.html'
    context_object_name = 'authors'
    paginate_by = 25

    def get_queryset(self):
        return Author.objects.prefetch_related('sources')


class AuthorDetailView(DetailView):
    model = Author
    template_name = 'library/author_detail.html'
    context_object_name = 'author'

    def get_queryset(self):
        return Author.objects.prefetch_related('sources')


class AuthorCreateView(CreateView):
    model = Author
    form_class = AuthorForm
    template_name = 'library/author_form.html'
    success_url = reverse_lazy('library:author_list')


class AuthorUpdateView(UpdateView):
    model = Author
    form_class = AuthorForm
    template_name = 'library/author_form.html'
    context_object_name = 'author'

    def get_success_url(self):
        return reverse_lazy('library:author_detail', kwargs={'pk': self.object.pk})


class AuthorDeleteView(DeleteView):
    model = Author
    template_name = 'library/author_confirm_delete.html'
    context_object_name = 'author'
    success_url = reverse_lazy('library:author_list')


class ProcessingCenterListView(ListView):
    model = Source
    template_name = 'library/processing_center.html'
    context_object_name = 'sources'
    paginate_by = 20

    def get_queryset(self):
        qs = apply_processing_center_filters(
            self.request,
            Source.objects.select_related('primary_domain').prefetch_related('authors'),
        )
        qs, self._stats_map = filter_sources_by_processing(self.request, qs)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        stats_map = getattr(self, '_stats_map', {})
        page_ids = [s.pk for s in context['sources']]
        if page_ids:
            page_stats = bulk_source_processing_stats(page_ids)
            stats_map.update(page_stats)
        for source in context['sources']:
            stats = stats_map.get(str(source.pk))
            source.processing = stats.to_dict() if stats else {}
            source.processing_pipeline = stats.pipeline if stats else []

        global_metrics = get_global_processing_metrics()
        context.update(
            {
                'global_metrics': global_metrics,
                'stats_map': stats_map,
                'processing_statuses': PROCESSING_STATUS_CHOICES,
                'quick_modes': QUICK_MODES,
                'source_types': Source.SourceType.choices,
                'priorities': Source.Priority.choices,
                'statuses': Source.Status.choices,
                'domains': Domain.objects.order_by('name'),
                'mode': self.request.GET.get('mode', ''),
                'filter_processing_status': self.request.GET.get('processing_status', ''),
                'filter_source_type': self.request.GET.get('source_type', ''),
                'filter_primary_domain': self.request.GET.get('primary_domain', ''),
                'filter_priority': self.request.GET.get('priority', ''),
                'filter_status': self.request.GET.get('status', ''),
                'filter_created_from': self.request.GET.get('created_from', ''),
                'filter_created_to': self.request.GET.get('created_to', ''),
                'filter_updated_from': self.request.GET.get('updated_from', ''),
                'filter_updated_to': self.request.GET.get('updated_to', ''),
                'query': self.request.GET.get('q', ''),
                'ordering': self.request.GET.get('ordering', '-updated_at'),
                'recent_activity': get_recent_activity(limit=20),
                'failed_ingestion_jobs': list(
                    DocumentIngestionJob.objects.filter(status=DocumentIngestionJob.Status.FAILED)
                    .select_related('source')
                    .order_by('-updated_at')[:8]
                ),
                'failed_batches_global': list(
                    ExtractionBatch.objects.exclude(parse_error='')
                    .select_related('source')
                    .order_by('-updated_at')[:8]
                ),
            }
        )
        context['pipeline_chart_labels_json'] = json.dumps([label for _, label in PIPELINE_LABELS])
        avg_pipeline = []
        if stats_map:
            for i, _key in enumerate(PIPELINE_LABELS):
                pcts = [s.pipeline[i]['pct'] for s in stats_map.values() if s.pipeline]
                avg_pipeline.append(int(sum(pcts) / len(pcts)) if pcts else 0)
        context['pipeline_chart_values_json'] = json.dumps(avg_pipeline)
        context['status_chart_labels_json'] = json.dumps(
            [label for _, label in PROCESSING_STATUS_CHOICES[:6]]
        )
        status_counts = {}
        for s in stats_map.values():
            status_counts[s.processing_status] = status_counts.get(s.processing_status, 0) + 1
        context['status_chart_values_json'] = json.dumps(
            [status_counts.get(k, 0) for k, _ in PROCESSING_STATUS_CHOICES[:6]]
        )
        return context


class ProcessingCenterExportCSVView(View):
    def get(self, request):
        qs = apply_processing_center_filters(
            request, Source.objects.select_related('primary_domain')
        )
        qs, stats_map = filter_sources_by_processing(request, qs)
        return export_processing_center_csv(list(qs), stats_map)
