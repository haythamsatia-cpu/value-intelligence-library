from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from .batch_quality import get_batch_quality_metrics
from .forms import (
    ExtractionBatchAiOutputForm,
    ExtractionBatchForm,
    ExtractionCandidateForm,
    ExtractionPromptTemplateForm,
    PromptSandboxForm,
)
from knowledge.models import KnowledgeUnit
from taxonomy.models import Domain

from .models import ExtractionBatch, ExtractionCandidate, ExtractionPromptTemplate
from .prompt_builder import build_prompt, build_prompt_for_batch
from .quality_profiles import PROFILE_CHOICES, QUALITY_PROFILES
from .parsers import bulk_fast_import_batches, fast_import_batch_ai_output, parse_batch_ai_output
from .services import (
    bulk_import_candidates,
    bulk_reject_candidates,
    flash_import_result,
    find_similar_knowledge_units,
    import_candidate_to_knowledge_unit,
    reject_candidate,
)


class DashboardView(TemplateView):
    template_name = 'ai_extraction/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_batches'] = ExtractionBatch.objects.count()
        context['pending_candidates'] = ExtractionCandidate.objects.filter(
            import_status=ExtractionCandidate.ImportStatus.PENDING
        ).count()
        context['imported_candidates'] = ExtractionCandidate.objects.filter(
            import_status=ExtractionCandidate.ImportStatus.IMPORTED
        ).count()
        context['active_templates'] = ExtractionPromptTemplate.objects.filter(is_active=True).count()
        context['recent_batches'] = ExtractionBatch.objects.select_related(
            'prompt_template', 'source', 'chapter'
        )[:10]
        return context


class PromptTemplateListView(ListView):
    model = ExtractionPromptTemplate
    template_name = 'ai_extraction/prompt_list.html'
    context_object_name = 'templates'
    paginate_by = 25

    def get_queryset(self):
        return ExtractionPromptTemplate.objects.select_related('source_domain')


class PromptTemplateDetailView(DetailView):
    model = ExtractionPromptTemplate
    template_name = 'ai_extraction/prompt_detail.html'
    context_object_name = 'template'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sample = self.request.GET.get('sample_text', '').strip() or (
            'Paste sample text on the prompt sandbox page to preview a full prompt.'
        )
        built = build_prompt(self.object, sample)
        context['built_prompt'] = built
        context['quality_profiles'] = QUALITY_PROFILES
        return context


class PromptTemplateCreateView(CreateView):
    model = ExtractionPromptTemplate
    form_class = ExtractionPromptTemplateForm
    template_name = 'ai_extraction/prompt_form.html'
    success_url = reverse_lazy('ai_extraction:prompt_list')


class PromptTemplateUpdateView(UpdateView):
    model = ExtractionPromptTemplate
    form_class = ExtractionPromptTemplateForm
    template_name = 'ai_extraction/prompt_form.html'
    context_object_name = 'template'

    def get_success_url(self):
        return reverse_lazy('ai_extraction:prompt_detail', kwargs={'pk': self.object.pk})


class PromptTemplateDeleteView(DeleteView):
    model = ExtractionPromptTemplate
    template_name = 'ai_extraction/prompt_confirm_delete.html'
    context_object_name = 'template'
    success_url = reverse_lazy('ai_extraction:prompt_list')


class BatchListView(ListView):
    model = ExtractionBatch
    template_name = 'ai_extraction/batch_list.html'
    context_object_name = 'batches'
    paginate_by = 25

    def get_queryset(self):
        qs = ExtractionBatch.objects.select_related('prompt_template', 'source', 'chapter')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        source_id = self.request.GET.get('source')
        if source_id:
            qs = qs.filter(source_id=source_id)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['statuses'] = ExtractionBatch.Status.choices
        context['filter_status'] = self.request.GET.get('status', '')
        context['filter_source'] = self.request.GET.get('source', '')
        return context


class BatchDetailView(DetailView):
    model = ExtractionBatch
    template_name = 'ai_extraction/batch_detail.html'
    context_object_name = 'batch'

    def get_queryset(self):
        return ExtractionBatch.objects.select_related(
            'prompt_template', 'source', 'chapter', 'prompt_template__source_domain'
        ).prefetch_related('candidates', 'text_chunks')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile_key = self.request.GET.get('profile', '').strip() or None
        built = build_prompt_for_batch(self.object, profile_key=profile_key)
        context['built_prompt'] = built
        context['combined_prompt'] = built.full_prompt
        context['json_instructions'] = built.json_schema
        context['applied_rules'] = built.applied_rules
        context['profile_key'] = profile_key
        context['quality_profiles'] = PROFILE_CHOICES
        context['batch_quality'] = get_batch_quality_metrics(self.object)
        context['ai_output_form'] = ExtractionBatchAiOutputForm(instance=self.object)
        preview_key = f'parse_preview_{self.object.pk}'
        context['parse_preview'] = self.request.session.pop(preview_key, None)
        fast_key = f'fast_import_preview_{self.object.pk}'
        context['fast_import_preview'] = self.request.session.pop(fast_key, None)
        return context


class BatchCreateView(CreateView):
    model = ExtractionBatch
    form_class = ExtractionBatchForm
    template_name = 'ai_extraction/batch_form.html'
    success_url = reverse_lazy('ai_extraction:batch_list')

    def get_initial(self):
        initial = super().get_initial()
        chapter_id = self.request.GET.get('chapter')
        source_id = self.request.GET.get('source')
        if chapter_id:
            initial['chapter'] = chapter_id
        if source_id:
            initial['source'] = source_id
        template_id = self.request.GET.get('prompt_template')
        if template_id:
            initial['prompt_template'] = template_id
        return initial


class BatchUpdateView(UpdateView):
    model = ExtractionBatch
    form_class = ExtractionBatchForm
    template_name = 'ai_extraction/batch_form.html'
    context_object_name = 'batch'

    def get_success_url(self):
        return reverse_lazy('ai_extraction:batch_detail', kwargs={'pk': self.object.pk})


class BatchDeleteView(DeleteView):
    model = ExtractionBatch
    template_name = 'ai_extraction/batch_confirm_delete.html'
    context_object_name = 'batch'
    success_url = reverse_lazy('ai_extraction:batch_list')


class BatchAiOutputUpdateView(View):
    """Save AI raw output and status from batch detail page."""

    def post(self, request, pk):
        batch = get_object_or_404(ExtractionBatch, pk=pk)
        form = ExtractionBatchAiOutputForm(request.POST, instance=batch)
        if form.is_valid():
            form.save()
            messages.success(request, 'AI output and status saved.')
        else:
            messages.error(request, 'Could not save AI output. Check the form.')
        return redirect('ai_extraction:batch_detail', pk=pk)


class BatchParseAiOutputView(View):
    """Parse ai_output_raw JSON into extraction candidates."""

    def post(self, request, pk):
        batch = get_object_or_404(ExtractionBatch, pk=pk)
        if not batch.ai_output_raw.strip():
            messages.error(request, 'Save AI output text before parsing.')
            return redirect('ai_extraction:batch_detail', pk=pk)

        preview = parse_batch_ai_output(batch)
        request.session[f'parse_preview_{batch.pk}'] = {
            'created': preview.created,
            'skipped_duplicates': preview.skipped_duplicates,
            'skipped_invalid': preview.skipped_invalid,
            'errors': preview.errors,
            'summary_lines': preview.summary_lines(),
        }

        if preview.created:
            messages.success(
                request,
                f'Parse complete: {preview.created} candidate(s) created.',
            )
        elif preview.skipped_duplicates and not preview.errors:
            messages.info(request, 'No new candidates — all titles already exist in this batch.')
        else:
            messages.warning(request, 'Parse finished with no new candidates. See summary below.')

        if preview.errors:
            messages.warning(
                request,
                f'{len(preview.errors)} validation issue(s) — see parse summary.',
            )

        return redirect('ai_extraction:batch_detail', pk=pk)


class BatchFastImportView(View):
    """Parse ai_output_raw JSON and create knowledge units directly (skip candidates)."""

    def post(self, request, pk):
        batch = get_object_or_404(ExtractionBatch, pk=pk)
        if not batch.ai_output_raw.strip():
            messages.error(request, 'Save AI output text before fast import.')
            return redirect('ai_extraction:batch_detail', pk=pk)

        preview = fast_import_batch_ai_output(batch)
        request.session[f'fast_import_preview_{batch.pk}'] = {
            'created': preview.created,
            'skipped_duplicates': preview.skipped_duplicates,
            'skipped_similar': preview.skipped_similar,
            'flagged_similar': preview.flagged_similar,
            'skipped_invalid': preview.skipped_invalid,
            'errors': preview.errors,
            'summary_lines': preview.summary_lines(),
        }

        if preview.created:
            messages.success(
                request,
                f'Fast import complete: {preview.created} knowledge unit(s) created (pending review).',
            )
        elif preview.skipped_duplicates and not preview.errors:
            messages.info(request, 'No new units — all titles already exist in the library.')
        else:
            messages.warning(request, 'Fast import finished with no new units. See summary below.')

        if preview.flagged_similar:
            messages.warning(
                request,
                f'{preview.flagged_similar} imported unit(s) have similar titles already in the library — review duplicates.',
            )
        if preview.errors:
            messages.warning(
                request,
                f'{len(preview.errors)} validation issue(s) — see fast import summary.',
            )

        return redirect('ai_extraction:batch_detail', pk=pk)


class CandidateListView(ListView):
    model = ExtractionCandidate
    template_name = 'ai_extraction/candidate_list.html'
    context_object_name = 'candidates'
    paginate_by = 25

    def get_queryset(self):
        qs = ExtractionCandidate.objects.select_related(
            'batch', 'proposed_domain', 'imported_knowledge_unit'
        )
        import_status = self.request.GET.get('import_status')
        if import_status:
            qs = qs.filter(import_status=import_status)
        batch_id = self.request.GET.get('batch')
        if batch_id:
            qs = qs.filter(batch_id=batch_id)
        source_id = self.request.GET.get('source')
        if source_id:
            qs = qs.filter(batch__source_id=source_id)
        domain_id = self.request.GET.get('proposed_domain')
        if domain_id:
            qs = qs.filter(proposed_domain_id=domain_id)
        knowledge_type = self.request.GET.get('proposed_knowledge_type')
        if knowledge_type:
            qs = qs.filter(proposed_knowledge_type=knowledge_type)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['import_statuses'] = ExtractionCandidate.ImportStatus.choices
        context['knowledge_types'] = KnowledgeUnit.KnowledgeType.choices
        context['domains'] = Domain.objects.order_by('name')
        context['filter_import_status'] = self.request.GET.get('import_status', '')
        context['filter_batch'] = self.request.GET.get('batch', '')
        context['filter_domain'] = self.request.GET.get('proposed_domain', '')
        context['filter_knowledge_type'] = self.request.GET.get('proposed_knowledge_type', '')
        context['filter_source'] = self.request.GET.get('source', '')
        context['batches'] = ExtractionBatch.objects.order_by('-updated_at')[:50]
        return context


class CandidateDetailView(DetailView):
    model = ExtractionCandidate
    template_name = 'ai_extraction/candidate_detail.html'
    context_object_name = 'candidate'

    def get_queryset(self):
        return ExtractionCandidate.objects.select_related(
            'batch', 'batch__source', 'batch__chapter', 'proposed_domain',
            'proposed_subdomain', 'proposed_topic', 'proposed_concept',
            'imported_knowledge_unit',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.object.import_status == ExtractionCandidate.ImportStatus.PENDING:
            context['similar_units'] = find_similar_knowledge_units(self.object.title)
        else:
            context['similar_units'] = []
        return context


class CandidateCreateView(CreateView):
    model = ExtractionCandidate
    form_class = ExtractionCandidateForm
    template_name = 'ai_extraction/candidate_form.html'

    def get_initial(self):
        initial = super().get_initial()
        batch_id = self.request.GET.get('batch')
        if batch_id:
            initial['batch'] = batch_id
            batch = ExtractionBatch.objects.filter(pk=batch_id).select_related('source').first()
            if batch and batch.source and batch.source.primary_domain_id:
                initial['proposed_domain'] = batch.source.primary_domain_id
        return initial

    def get_success_url(self):
        return reverse_lazy('ai_extraction:candidate_detail', kwargs={'pk': self.object.pk})


class CandidateUpdateView(UpdateView):
    model = ExtractionCandidate
    form_class = ExtractionCandidateForm
    template_name = 'ai_extraction/candidate_form.html'
    context_object_name = 'candidate'

    def get_success_url(self):
        return reverse_lazy('ai_extraction:candidate_detail', kwargs={'pk': self.object.pk})


class CandidateImportView(View):
    def post(self, request, pk):
        candidate = get_object_or_404(ExtractionCandidate, pk=pk)
        if candidate.import_status == ExtractionCandidate.ImportStatus.REJECTED:
            messages.warning(request, 'Rejected candidates cannot be imported.')
            next_url = request.POST.get('next_url')
            if next_url:
                return redirect(next_url)
            return redirect('ai_extraction:candidate_detail', pk=pk)
        unit, similar = import_candidate_to_knowledge_unit(candidate)
        flash_import_result(request, unit, candidate, similar)
        next_url = request.POST.get('next_url')
        if next_url:
            return redirect(next_url)
        if unit:
            return redirect('knowledge:knowledgeunit_detail', pk=unit.pk)
        return redirect('ai_extraction:candidate_detail', pk=pk)


class CandidateBulkImportView(View):
    def post(self, request):
        ids = request.POST.getlist('candidate_ids')
        if not ids:
            messages.warning(request, 'Select at least one candidate.')
            return redirect('ai_extraction:candidate_list')
        stats = bulk_import_candidates(ids)
        if stats['imported']:
            messages.success(request, f'Bulk import: {stats["imported"]} knowledge unit(s) created.')
        if stats['failed']:
            messages.error(
                request,
                f'Bulk import: {stats["failed"]} failed (missing domain).',
            )
        for warning in stats['warnings'][:10]:
            messages.warning(request, warning)
        return redirect(request.POST.get('next') or 'ai_extraction:candidate_list')


class CandidateBulkRejectView(View):
    def post(self, request):
        ids = request.POST.getlist('candidate_ids')
        if not ids:
            messages.warning(request, 'Select at least one candidate.')
            return redirect('ai_extraction:candidate_list')
        count = bulk_reject_candidates(ids)
        messages.success(request, f'Rejected {count} candidate(s).')
        return redirect(request.POST.get('next') or 'ai_extraction:candidate_list')


class CandidateRejectView(View):
    def post(self, request, pk):
        candidate = get_object_or_404(ExtractionCandidate, pk=pk)
        if candidate.import_status == ExtractionCandidate.ImportStatus.IMPORTED:
            messages.warning(request, 'Already imported; cannot reject.')
            return redirect('ai_extraction:candidate_detail', pk=pk)
        reject_candidate(candidate)
        messages.success(request, f'Candidate "{candidate.title}" rejected.')
        next_url = request.POST.get('next_url')
        if next_url:
            return redirect(next_url)
        return redirect('ai_extraction:candidate_detail', pk=pk)


class PromptSandboxView(TemplateView):
    template_name = 'ai_extraction/prompt_sandbox.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = PromptSandboxForm(self.request.GET or None)
        context['built_prompt'] = None
        context['quality_profiles'] = QUALITY_PROFILES

        if self.request.GET.get('preview'):
            form = PromptSandboxForm(self.request.GET)
            context['form'] = form
            if form.is_valid():
                template = form.cleaned_data['prompt_template']
                profile = form.cleaned_data.get('quality_profile') or None
                source = form.cleaned_data.get('source')
                context['built_prompt'] = build_prompt(
                    template,
                    form.cleaned_data['sample_text'],
                    source=source,
                    profile_key=profile,
                )
                context['behavior_estimate'] = _sandbox_behavior_estimate(
                    template, profile
                )
        return context


def _sandbox_behavior_estimate(template, profile_key):
    from .quality_profiles import EffectiveTemplateSettings

    settings = EffectiveTemplateSettings(template, profile_key=profile_key)
    profiles = QUALITY_PROFILES.get(profile_key) if profile_key else None
    lines = [
        f'Expected granularity: {settings.target_granularity}',
        f'Quality bar: {settings.minimum_quality_threshold}',
        f'Style: {settings.extraction_style}',
    ]
    if profiles:
        lines.append(f'Profile: {profiles.description}')
    if settings.require_page_references:
        lines.append('Will emphasize page references and traceability in JSON schema.')
    if settings.avoid_generic_filler:
        lines.append('Filler avoidance rules are active.')
    return lines
