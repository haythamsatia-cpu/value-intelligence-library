from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView

from .forms import DocumentIngestionJobForm, IngestionManualTextForm, PromptTemplateSelectForm
from .ingestion_services import (
    bulk_create_batches_from_job,
    create_batch_from_chunk,
    create_text_chunks,
    extract_pdf_text,
)
from .models import DocumentIngestionJob, ExtractionBatch, ExtractionPromptTemplate, TextChunk
from .parsers import bulk_fast_import_batches


class IngestionJobListView(ListView):
    model = DocumentIngestionJob
    template_name = 'ai_extraction/ingestion_list.html'
    context_object_name = 'jobs'
    paginate_by = 25

    def get_queryset(self):
        qs = DocumentIngestionJob.objects.select_related('source')
        source_id = self.request.GET.get('source')
        if source_id:
            qs = qs.filter(source_id=source_id)
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['statuses'] = DocumentIngestionJob.Status.choices
        context['filter_status'] = self.request.GET.get('status', '')
        context['filter_source'] = self.request.GET.get('source', '')
        return context


class IngestionJobDetailView(DetailView):
    model = DocumentIngestionJob
    template_name = 'ai_extraction/ingestion_detail.html'
    context_object_name = 'job'

    def get_queryset(self):
        return DocumentIngestionJob.objects.select_related('source').prefetch_related('chunks')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['manual_text_form'] = IngestionManualTextForm(instance=self.object)
        context['bulk_batch_form'] = PromptTemplateSelectForm()
        context['chunk_count'] = self.object.chunks.count()
        context['chunks_without_batch'] = self.object.chunks.filter(
            created_batch__isnull=True
        ).count()
        job_batches = ExtractionBatch.objects.filter(
            text_chunks__ingestion_job=self.object
        ).distinct()
        context['job_batches'] = job_batches
        context['batches_with_ai_output'] = job_batches.exclude(ai_output_raw='').count()
        context['fast_import_preview'] = self.request.session.pop(
            f'ingestion_fast_import_{self.object.pk}', None
        )
        return context


class IngestionJobCreateView(CreateView):
    model = DocumentIngestionJob
    form_class = DocumentIngestionJobForm
    template_name = 'ai_extraction/ingestion_form.html'

    def get_initial(self):
        initial = super().get_initial()
        source_id = self.request.GET.get('source')
        if source_id:
            initial['source'] = source_id
        return initial

    def get_success_url(self):
        return reverse_lazy('ai_extraction:ingestion_detail', kwargs={'pk': self.object.pk})


class IngestionJobDeleteView(DeleteView):
    model = DocumentIngestionJob
    template_name = 'ai_extraction/ingestion_confirm_delete.html'
    context_object_name = 'job'
    success_url = reverse_lazy('ai_extraction:ingestion_list')


class IngestionExtractTextView(View):
    def post(self, request, pk):
        job = get_object_or_404(DocumentIngestionJob, pk=pk)
        result = extract_pdf_text(job)
        if result.success:
            messages.success(request, result.message)
        else:
            messages.error(request, result.message)
        return redirect('ai_extraction:ingestion_detail', pk=pk)


class IngestionSaveManualTextView(View):
    def post(self, request, pk):
        job = get_object_or_404(DocumentIngestionJob, pk=pk)
        form = IngestionManualTextForm(request.POST, instance=job)
        if form.is_valid():
            job = form.save(commit=False)
            if job.extracted_text.strip():
                job.status = DocumentIngestionJob.Status.EXTRACTED
                job.error_message = ''
            job.save()
            messages.success(request, 'Manual text saved.')
        else:
            messages.error(request, 'Could not save manual text.')
        return redirect('ai_extraction:ingestion_detail', pk=pk)


class IngestionCreateChunksView(View):
    def post(self, request, pk):
        job = get_object_or_404(DocumentIngestionJob, pk=pk)
        chunk_size = int(request.POST.get('chunk_size', 12000))
        chunk_size = max(5000, min(chunk_size, 20000))
        result = create_text_chunks(job, chunk_size=chunk_size)
        if result.created:
            messages.success(request, result.message)
        else:
            messages.warning(request, result.message)
        return redirect('ai_extraction:ingestion_detail', pk=pk)


class IngestionBulkBatchesView(View):
    def post(self, request, pk):
        job = get_object_or_404(DocumentIngestionJob, pk=pk)
        form = PromptTemplateSelectForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Select a valid prompt template.')
            return redirect('ai_extraction:ingestion_detail', pk=pk)
        result = bulk_create_batches_from_job(job, form.cleaned_data['prompt_template'])
        if result.created:
            messages.success(request, f'Created {result.created} extraction batch(es).')
        if result.skipped:
            messages.info(request, f'{result.skipped} chunk(s) already had batches.')
        for err in result.errors[:5]:
            messages.warning(request, err)
        if not result.created and not result.errors:
            messages.warning(request, 'No chunks without batches found. Create chunks first.')
        return redirect('ai_extraction:ingestion_detail', pk=pk)


class IngestionBulkFastImportView(View):
    """Parse & fast import all job batches that have saved AI output."""

    def post(self, request, pk):
        job = get_object_or_404(DocumentIngestionJob, pk=pk)
        batches = (
            ExtractionBatch.objects.filter(text_chunks__ingestion_job=job)
            .exclude(ai_output_raw='')
            .distinct()
        )
        if not batches.exists():
            messages.error(
                request,
                'No batches with saved AI output found for this ingestion job.',
            )
            return redirect('ai_extraction:ingestion_detail', pk=pk)

        preview = bulk_fast_import_batches(batches)
        request.session[f'ingestion_fast_import_{job.pk}'] = {
            'created': preview.created,
            'skipped_duplicates': preview.skipped_duplicates,
            'skipped_similar': preview.skipped_similar,
            'flagged_similar': preview.flagged_similar,
            'skipped_invalid': preview.skipped_invalid,
            'errors': preview.errors,
            'summary_lines': preview.summary_lines(),
            'batch_count': batches.count(),
        }

        if preview.created:
            messages.success(
                request,
                f'Bulk fast import: {preview.created} knowledge unit(s) created across {batches.count()} batch(es).',
            )
        else:
            messages.warning(request, 'Bulk fast import completed with no new units. See summary on this page.')

        if preview.errors:
            messages.warning(request, f'{len(preview.errors)} validation issue(s) — see summary below.')

        return redirect('ai_extraction:ingestion_detail', pk=pk)


class TextChunkListView(ListView):
    model = TextChunk
    template_name = 'ai_extraction/chunk_list.html'
    context_object_name = 'chunks'
    paginate_by = 25

    def get_queryset(self):
        qs = TextChunk.objects.select_related('source', 'ingestion_job', 'created_batch')
        job_id = self.request.GET.get('job')
        if job_id:
            qs = qs.filter(ingestion_job_id=job_id)
        source_id = self.request.GET.get('source')
        if source_id:
            qs = qs.filter(source_id=source_id)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_job'] = self.request.GET.get('job', '')
        context['filter_source'] = self.request.GET.get('source', '')
        return context


class TextChunkDetailView(DetailView):
    model = TextChunk
    template_name = 'ai_extraction/chunk_detail.html'
    context_object_name = 'chunk'

    def get_queryset(self):
        return TextChunk.objects.select_related(
            'source', 'chapter', 'ingestion_job', 'created_batch'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['batch_form'] = PromptTemplateSelectForm()
        return context


class TextChunkCreateBatchView(View):
    def post(self, request, pk):
        chunk = get_object_or_404(TextChunk, pk=pk)
        form = PromptTemplateSelectForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Select a valid prompt template.')
            return redirect('ai_extraction:chunk_detail', pk=pk)
        if chunk.created_batch_id:
            messages.info(request, 'Batch already exists for this chunk.')
            return redirect('ai_extraction:batch_detail', pk=chunk.created_batch_id)
        batch = create_batch_from_chunk(chunk, form.cleaned_data['prompt_template'])
        messages.success(request, f'Created extraction batch: {batch.title}')
        return redirect('ai_extraction:batch_detail', pk=batch.pk)
