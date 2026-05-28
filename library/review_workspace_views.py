from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from ai_extraction.services import (
    bulk_import_candidates,
    bulk_reject_candidates,
    flash_import_result,
    import_candidate_to_knowledge_unit,
    reject_candidate,
)
from ai_extraction.models import ExtractionCandidate
from knowledge.models import KnowledgeUnit
from knowledge.taxonomy_cleanup import apply_taxonomy_cleanup_bulk_update
from knowledge.views import _apply_bulk_action
from taxonomy.models import Concept, Domain, Subdomain, Tag, Topic

from .models import Source
from .review_workspace import (
    WORKSPACE_TABS,
    apply_candidate_filters,
    apply_knowledge_filters,
    apply_knowledge_tab,
    candidate_page_reference,
    get_review_workspace_metrics,
    get_review_workspace_pipeline,
    source_candidates_queryset,
    source_knowledge_queryset,
    workspace_filter_context,
)


class SourceReviewWorkspaceView(View):
    """Book-level review: candidates + knowledge units for one source."""

    paginate_by = 50

    def get(self, request, pk):
        source = get_object_or_404(Source.objects.select_related('primary_domain'), pk=pk)
        tab = request.GET.get('tab', 'candidates')
        if tab not in dict(WORKSPACE_TABS):
            tab = 'candidates'

        show_candidates = tab == 'candidates'
        page_obj = None
        candidates = []
        knowledge_units = []

        if show_candidates:
            qs = apply_candidate_filters(request, source_candidates_queryset(source))
            paginator = Paginator(qs, self.paginate_by)
            page_obj = paginator.get_page(request.GET.get('page'))
            candidates = page_obj.object_list
            for candidate in candidates:
                candidate.page_ref = candidate_page_reference(candidate)
        else:
            qs = apply_knowledge_filters(
                request, apply_knowledge_tab(source_knowledge_queryset(source), tab)
            )
            paginator = Paginator(qs, self.paginate_by)
            page_obj = paginator.get_page(request.GET.get('page'))
            knowledge_units = page_obj.object_list

        context = {
            'source': source,
            'workspace_tabs': WORKSPACE_TABS,
            'show_candidates': show_candidates,
            'candidates': candidates,
            'knowledge_units': knowledge_units,
            'page_obj': page_obj,
            'metrics': get_review_workspace_metrics(source),
            'review_pipeline': get_review_workspace_pipeline(source),
            'domains': Domain.objects.order_by('name'),
            'subdomains': Subdomain.objects.select_related('domain').order_by('domain__name', 'name'),
            'topics': Topic.objects.select_related('subdomain__domain').order_by(
                'subdomain__domain__name', 'subdomain__name', 'name'
            ),
            'concepts': Concept.objects.select_related('topic__subdomain__domain').order_by(
                'topic__subdomain__domain__name', 'topic__subdomain__name', 'topic__name', 'name'
            ),
            'all_tags': Tag.objects.order_by('name'),
            'knowledge_types': KnowledgeUnit.KnowledgeType.choices,
            'review_statuses': KnowledgeUnit.ReviewStatus.choices,
            'governance_statuses': KnowledgeUnit.GovernanceStatus.choices,
            'imported_via_choices': KnowledgeUnit.ImportedVia.choices,
            'import_statuses': ExtractionCandidate.ImportStatus.choices,
            'value_levels': KnowledgeUnit.ValueLevel.choices,
            'next_url': request.get_full_path(),
        }
        context.update(workspace_filter_context(request, source))
        return render(request, 'library/source_review_workspace.html', context)


class SourceReviewWorkspaceBulkView(View):
    """Bulk and scoped actions from the review workspace."""

    def post(self, request, pk):
        source = get_object_or_404(Source, pk=pk)
        next_url = request.POST.get('next_url') or reverse(
            'library:source_review_workspace', kwargs={'pk': pk}
        )
        scope = request.POST.get('scope', 'units')
        bulk_action = request.POST.get('bulk_action', '').strip()

        if scope == 'candidates':
            ids = request.POST.getlist('candidate_ids')
            if not ids:
                messages.warning(request, 'Select at least one candidate.')
                return redirect(next_url)
            if bulk_action == 'import_candidates':
                stats = bulk_import_candidates(ids)
                if stats['imported']:
                    messages.success(
                        request, f'Imported {stats["imported"]} candidate(s) as knowledge units.'
                    )
                if stats['failed']:
                    messages.error(request, f'{stats["failed"]} import(s) failed (missing domain).')
                if stats['skipped']:
                    messages.info(request, f'Skipped {stats["skipped"]} non-pending candidate(s).')
                for warning in stats['warnings'][:8]:
                    messages.warning(request, warning)
            elif bulk_action == 'reject_candidates':
                count = bulk_reject_candidates(ids)
                messages.success(request, f'Rejected {count} candidate(s).')
            else:
                messages.warning(request, 'Unknown candidate bulk action.')
            return redirect(next_url)

        unit_ids = request.POST.getlist('unit_ids')
        if not unit_ids:
            messages.warning(request, 'Select at least one knowledge unit.')
            return redirect(next_url)

        queryset = source_knowledge_queryset(source).filter(pk__in=unit_ids)
        if bulk_action == 'taxonomy_update':
            for msg in apply_taxonomy_cleanup_bulk_update(request, queryset):
                if 'nothing changed' in msg:
                    messages.info(request, msg)
                else:
                    messages.success(request, msg)
        elif bulk_action:
            _apply_bulk_action(request, queryset, action=bulk_action)
        else:
            messages.warning(request, 'Select a bulk action.')
        return redirect(next_url)


class SourceReviewWorkspaceCandidateActionView(View):
    """Inline import/reject for a single candidate."""

    def post(self, request, pk, candidate_pk):
        source = get_object_or_404(Source, pk=pk)
        candidate = get_object_or_404(
            ExtractionCandidate.objects.filter(batch__source=source), pk=candidate_pk
        )
        next_url = request.POST.get('next_url') or reverse(
            'library:source_review_workspace', kwargs={'pk': pk}
        )
        action = request.POST.get('action')

        if action == 'import':
            if candidate.import_status == ExtractionCandidate.ImportStatus.REJECTED:
                messages.warning(request, 'Rejected candidates cannot be imported.')
            else:
                unit, similar = import_candidate_to_knowledge_unit(candidate)
                flash_import_result(request, unit, candidate, similar)
        elif action == 'reject':
            if candidate.import_status == ExtractionCandidate.ImportStatus.IMPORTED:
                messages.warning(request, 'Already imported; cannot reject.')
            else:
                reject_candidate(candidate)
                messages.success(request, f'Rejected: {candidate.title}')
        else:
            messages.warning(request, 'Unknown action.')
        return redirect(next_url)
