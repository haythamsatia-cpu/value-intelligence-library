import uuid
import json
from datetime import timedelta

from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from library.models import Source
from taxonomy.models import Domain, Tag
from taxonomy.utils import get_or_create_uncategorized_domain

from .exports import export_knowledge_units_csv
from .forms import KnowledgeRelationshipForm, KnowledgeUnitForm
from .models import KnowledgeRelationship, KnowledgeUnit
from .taxonomy_cleanup import (
    QUICK_BULK_ACTIONS,
    apply_taxonomy_cleanup_bulk_update,
    get_cleanup_summary_metrics,
    get_taxonomy_cleanup_queryset,
    taxonomy_cleanup_filter_context,
)


def _base_knowledge_queryset():
    return KnowledgeUnit.objects.select_related(
        'domain', 'subdomain', 'topic', 'concept', 'source', 'chapter', 'reviewed_by'
    ).prefetch_related('tags')


def _apply_knowledge_filters(request, qs):
    qs = KnowledgeUnit.objects.select_related(
        'domain', 'subdomain', 'topic', 'concept', 'source', 'chapter', 'reviewed_by'
    ).prefetch_related('tags') if qs is None else qs
    domain_id = request.GET.get('domain')
    if domain_id:
        qs = qs.filter(domain_id=domain_id)
    source_id = request.GET.get('source')
    if source_id:
        qs = qs.filter(source_id=source_id)
    review_status = request.GET.get('review_status')
    if review_status:
        qs = qs.filter(review_status=review_status)
    consulting_value = request.GET.get('consulting_value')
    if consulting_value:
        qs = qs.filter(consulting_value=consulting_value)
    teaching_value = request.GET.get('teaching_value')
    if teaching_value:
        qs = qs.filter(teaching_value=teaching_value)
    confidence_level = request.GET.get('confidence_level')
    if confidence_level:
        qs = qs.filter(confidence_level=confidence_level)
    source_quality = request.GET.get('source_quality')
    if source_quality:
        qs = qs.filter(source_quality=source_quality)
    governance_status = request.GET.get('governance_status')
    if governance_status:
        qs = qs.filter(governance_status=governance_status)
    duplicate_flag = request.GET.get('duplicate')
    if duplicate_flag == 'yes':
        qs = qs.filter(is_duplicate=True)
    elif duplicate_flag == 'no':
        qs = qs.filter(is_duplicate=False)
    difficulty_level = request.GET.get('difficulty_level')
    if difficulty_level:
        qs = qs.filter(difficulty_level=difficulty_level)
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(executive_insight__icontains=q)
            | Q(detailed_explanation__icontains=q)
            | Q(practical_application__icontains=q)
            | Q(consultant_use_case__icontains=q)
            | Q(course_use_case__icontains=q)
            | Q(keywords__icontains=q)
            | Q(personal_commentary__icontains=q)
            | Q(approval_notes__icontains=q)
        )

    ordering = request.GET.get('ordering', '-updated_at')
    ordering_map = {
        '-updated_at': '-updated_at',
        'title': 'title',
        '-created_at': '-created_at',
        'consulting_value': 'consulting_value',
        'teaching_value': 'teaching_value',
    }
    qs = qs.order_by(ordering_map.get(ordering, '-updated_at'))
    return qs


def _find_possible_duplicates(unit: KnowledgeUnit, limit=8):
    title = unit.title.strip()
    if not title:
        return KnowledgeUnit.objects.none()
    q = Q(title__iexact=title) | Q(title__icontains=title) | Q()
    # Avoid huge query text when title is very long.
    if len(title) > 3:
        q = q | Q(title__icontains=title[:80])
    return KnowledgeUnit.objects.filter(q).exclude(pk=unit.pk).order_by('-updated_at')[:limit]


def _review_mode_queryset(mode: str):
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    qs = _base_knowledge_queryset()
    if mode == 'high_consulting':
        return qs.filter(consulting_value=KnowledgeUnit.ValueLevel.HIGH)
    if mode == 'high_teaching':
        return qs.filter(teaching_value=KnowledgeUnit.ValueLevel.HIGH)
    if mode == 'possible_duplicates':
        return qs.filter(is_duplicate=True)
    if mode == 'recently_imported':
        return qs.filter(review_status=KnowledgeUnit.ReviewStatus.AI_EXTRACTED, created_at__gte=week_ago)
    if mode == 'low_confidence':
        return qs.filter(confidence_level=KnowledgeUnit.ValueLevel.LOW)
    if mode == 'uncategorized':
        return qs.filter(domain=get_or_create_uncategorized_domain())
    return qs.filter(
        review_status=KnowledgeUnit.ReviewStatus.AI_EXTRACTED,
        governance_status=KnowledgeUnit.GovernanceStatus.PENDING_REVIEW,
    )


def _apply_bulk_action(request, queryset, action=None):
    action = action or request.POST.get('bulk_action')
    if not action:
        messages.warning(request, 'Select a bulk action.')
        return

    if action == 'bulk_approve':
        count = queryset.update(
            governance_status=KnowledgeUnit.GovernanceStatus.APPROVED,
            review_status=KnowledgeUnit.ReviewStatus.APPROVED,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        messages.success(request, f'Approved {count} knowledge unit(s).')
    elif action == 'bulk_archive':
        count = queryset.update(
            governance_status=KnowledgeUnit.GovernanceStatus.ARCHIVED,
            review_status=KnowledgeUnit.ReviewStatus.ARCHIVED,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        messages.success(request, f'Archived {count} knowledge unit(s).')
    elif action == 'bulk_set_reviewed':
        count = queryset.update(
            governance_status=KnowledgeUnit.GovernanceStatus.REVIEWED,
            review_status=KnowledgeUnit.ReviewStatus.REVIEWED,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        messages.success(request, f'Marked reviewed: {count} unit(s).')
    elif action == 'bulk_change_domain':
        domain_id = request.POST.get('bulk_domain')
        if not domain_id:
            messages.error(request, 'Choose a domain for bulk change.')
            return
        count = queryset.update(domain_id=domain_id)
        messages.success(request, f'Updated domain for {count} unit(s).')
    elif action == 'bulk_assign_tags':
        tag_ids = request.POST.getlist('bulk_tags')
        if not tag_ids:
            messages.error(request, 'Choose one or more tags.')
            return
        tags = Tag.objects.filter(pk__in=tag_ids)
        count = 0
        for unit in queryset:
            unit.tags.add(*tags)
            count += 1
        messages.success(request, f'Assigned tags to {count} unit(s).')
    elif action == 'bulk_set_consulting':
        value = request.POST.get('bulk_consulting_value')
        if value not in dict(KnowledgeUnit.ValueLevel.choices):
            messages.error(request, 'Choose a valid consulting value.')
            return
        count = queryset.update(consulting_value=value)
        messages.success(request, f'Updated consulting value for {count} unit(s).')
    elif action == 'bulk_set_teaching':
        value = request.POST.get('bulk_teaching_value')
        if value not in dict(KnowledgeUnit.ValueLevel.choices):
            messages.error(request, 'Choose a valid teaching value.')
            return
        count = queryset.update(teaching_value=value)
        messages.success(request, f'Updated teaching value for {count} unit(s).')
    elif action == 'bulk_set_confidence':
        value = request.POST.get('bulk_confidence_level')
        if value not in dict(KnowledgeUnit.ValueLevel.choices):
            messages.error(request, 'Choose a valid confidence level.')
            return
        count = queryset.update(confidence_level=value)
        messages.success(request, f'Updated confidence level for {count} unit(s).')
    elif action == 'bulk_mark_duplicate':
        duplicate_group = uuid.uuid4()
        count = queryset.update(is_duplicate=True, duplicate_group=duplicate_group)
        messages.success(request, f'Marked duplicate: {count} unit(s).')
    elif action == 'bulk_unmark_duplicate':
        count = queryset.update(is_duplicate=False, duplicate_group=None)
        messages.success(request, f'Removed duplicate flag from {count} unit(s).')
    else:
        messages.warning(request, 'Unknown bulk action.')


class KnowledgeUnitListView(ListView):
    model = KnowledgeUnit
    template_name = 'knowledge/knowledgeunit_list.html'
    context_object_name = 'knowledge_units'
    paginate_by = 25

    def get_queryset(self):
        return _apply_knowledge_filters(self.request, _base_knowledge_queryset())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['domains'] = Domain.objects.order_by('name')
        context['sources'] = Source.objects.order_by('title')
        context['filter_domain'] = self.request.GET.get('domain', '')
        context['filter_source'] = self.request.GET.get('source', '')
        context['filter_review_status'] = self.request.GET.get('review_status', '')
        context['filter_consulting_value'] = self.request.GET.get('consulting_value', '')
        context['filter_teaching_value'] = self.request.GET.get('teaching_value', '')
        context['filter_difficulty_level'] = self.request.GET.get('difficulty_level', '')
        context['filter_confidence_level'] = self.request.GET.get('confidence_level', '')
        context['filter_source_quality'] = self.request.GET.get('source_quality', '')
        context['filter_governance_status'] = self.request.GET.get('governance_status', '')
        context['filter_duplicate'] = self.request.GET.get('duplicate', '')
        context['query'] = self.request.GET.get('q', '')
        context['ordering'] = self.request.GET.get('ordering', '-updated_at')
        context['view_mode'] = self.request.GET.get('view', 'table')
        context['review_statuses'] = KnowledgeUnit.ReviewStatus.choices
        context['value_levels'] = KnowledgeUnit.ValueLevel.choices
        context['difficulty_levels'] = KnowledgeUnit.DifficultyLevel.choices
        context['governance_statuses'] = KnowledgeUnit.GovernanceStatus.choices
        context['all_tags'] = Tag.objects.order_by('name')
        context['saved_modes'] = [
            ('pending_review', 'Pending Review'),
            ('high_consulting', 'High Consulting Value'),
            ('high_teaching', 'High Teaching Value'),
            ('possible_duplicates', 'Possible Duplicates'),
            ('recently_imported', 'Recently Imported'),
            ('low_confidence', 'Low Confidence'),
        ]
        return context


class KnowledgeUnitDetailView(DetailView):
    model = KnowledgeUnit
    template_name = 'knowledge/knowledgeunit_detail.html'
    context_object_name = 'knowledge_unit'

    def get_queryset(self):
        return KnowledgeUnit.objects.select_related(
            'domain', 'subdomain', 'topic', 'concept', 'source', 'chapter', 'reviewed_by'
        ).prefetch_related(
            'tags',
            'outgoing_relationships__to_knowledge_unit',
            'incoming_relationships__from_knowledge_unit',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['possible_duplicates'] = _find_possible_duplicates(self.object)
        return context


class KnowledgeUnitCreateView(CreateView):
    model = KnowledgeUnit
    form_class = KnowledgeUnitForm
    template_name = 'knowledge/knowledgeunit_form.html'
    success_url = reverse_lazy('knowledge:knowledgeunit_list')


class KnowledgeUnitUpdateView(UpdateView):
    model = KnowledgeUnit
    form_class = KnowledgeUnitForm
    template_name = 'knowledge/knowledgeunit_form.html'
    context_object_name = 'knowledge_unit'

    def get_success_url(self):
        return reverse_lazy('knowledge:knowledgeunit_detail', kwargs={'pk': self.object.pk})


class KnowledgeUnitDeleteView(DeleteView):
    model = KnowledgeUnit
    template_name = 'knowledge/knowledgeunit_confirm_delete.html'
    context_object_name = 'knowledge_unit'
    success_url = reverse_lazy('knowledge:knowledgeunit_list')


class KnowledgeUnitExportCSVView(View):
    def get(self, request):
        return export_knowledge_units_csv(_apply_knowledge_filters(request, _base_knowledge_queryset()))


class KnowledgeReviewQueueView(ListView):
    model = KnowledgeUnit
    template_name = 'knowledge/review_queue.html'
    context_object_name = 'knowledge_units'
    paginate_by = 25

    def get_queryset(self):
        mode = self.request.GET.get('mode', 'pending_review')
        qs = _review_mode_queryset(mode)
        return _apply_knowledge_filters(self.request, qs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for unit in context['knowledge_units']:
            unit.has_possible_duplicates = KnowledgeUnit.objects.filter(
                title__icontains=unit.title[:60]
            ).exclude(pk=unit.pk).exists()
        qs_all = _base_knowledge_queryset()
        week_ago = timezone.now() - timedelta(days=7)
        domain_counts = list(
            qs_all.values('domain__name').annotate(total=Count('id')).order_by('-total')[:8]
        )
        status_counts = list(
            qs_all.values('governance_status').annotate(total=Count('id')).order_by('governance_status')
        )
        value_counts = list(
            qs_all.values('consulting_value').annotate(total=Count('id')).order_by('consulting_value')
        )
        context.update(
            {
                'domains': Domain.objects.order_by('name'),
                'sources': Source.objects.order_by('title'),
                'review_statuses': KnowledgeUnit.ReviewStatus.choices,
                'value_levels': KnowledgeUnit.ValueLevel.choices,
                'difficulty_levels': KnowledgeUnit.DifficultyLevel.choices,
                'governance_statuses': KnowledgeUnit.GovernanceStatus.choices,
                'query': self.request.GET.get('q', ''),
                'ordering': self.request.GET.get('ordering', '-updated_at'),
                'filter_domain': self.request.GET.get('domain', ''),
                'filter_source': self.request.GET.get('source', ''),
                'filter_review_status': self.request.GET.get('review_status', ''),
                'filter_consulting_value': self.request.GET.get('consulting_value', ''),
                'filter_teaching_value': self.request.GET.get('teaching_value', ''),
                'filter_confidence_level': self.request.GET.get('confidence_level', ''),
                'filter_source_quality': self.request.GET.get('source_quality', ''),
                'filter_governance_status': self.request.GET.get('governance_status', ''),
                'filter_duplicate': self.request.GET.get('duplicate', ''),
                'mode': self.request.GET.get('mode', 'pending_review'),
                'saved_modes': [
                    ('pending_review', 'Pending Review'),
                    ('high_consulting', 'High Consulting Value'),
                    ('high_teaching', 'High Teaching Value'),
                    ('possible_duplicates', 'Possible Duplicates'),
                    ('recently_imported', 'Recently Imported'),
                    ('low_confidence', 'Low Confidence'),
                    ('uncategorized', 'Uncategorized Domain'),
                ],
                'uncategorized_domain': get_or_create_uncategorized_domain(),
                'all_tags': Tag.objects.order_by('name'),
                'metrics': {
                    'total': qs_all.count(),
                    'approved': qs_all.filter(governance_status=KnowledgeUnit.GovernanceStatus.APPROVED).count(),
                    'pending': qs_all.filter(governance_status=KnowledgeUnit.GovernanceStatus.PENDING_REVIEW).count(),
                    'duplicates': qs_all.filter(is_duplicate=True).count(),
                    'imported_this_week': qs_all.filter(created_at__gte=week_ago).count(),
                    'fast_imported': qs_all.filter(
                        imported_via=KnowledgeUnit.ImportedVia.FAST_IMPORT
                    ).count(),
                    'candidate_reviewed': qs_all.filter(
                        imported_via=KnowledgeUnit.ImportedVia.CANDIDATE_REVIEW
                    ).count(),
                },
                'domain_chart_labels': [row['domain__name'] or 'Unassigned' for row in domain_counts],
                'domain_chart_values': [row['total'] for row in domain_counts],
                'status_chart_labels': [row['governance_status'] for row in status_counts],
                'status_chart_values': [row['total'] for row in status_counts],
                'value_chart_labels': [row['consulting_value'] for row in value_counts],
                'value_chart_values': [row['total'] for row in value_counts],
            }
        )
        context['domain_chart_labels_json'] = json.dumps(context['domain_chart_labels'])
        context['domain_chart_values_json'] = json.dumps(context['domain_chart_values'])
        context['status_chart_labels_json'] = json.dumps(context['status_chart_labels'])
        context['status_chart_values_json'] = json.dumps(context['status_chart_values'])
        context['value_chart_labels_json'] = json.dumps(context['value_chart_labels'])
        context['value_chart_values_json'] = json.dumps(context['value_chart_values'])
        return context


class KnowledgeUnitBulkActionView(View):
    def post(self, request):
        selected_ids = request.POST.getlist('unit_ids')
        if not selected_ids:
            messages.warning(request, 'Select at least one knowledge unit.')
            return redirect(request.POST.get('next_url') or 'knowledge:knowledgeunit_list')
        queryset = KnowledgeUnit.objects.filter(id__in=selected_ids)
        _apply_bulk_action(request, queryset)
        return redirect(request.POST.get('next_url') or 'knowledge:knowledgeunit_list')


class TaxonomyCleanupListView(ListView):
    model = KnowledgeUnit
    template_name = 'knowledge/taxonomy_cleanup.html'
    context_object_name = 'knowledge_units'
    paginate_by = 25

    def get_queryset(self):
        qs = get_taxonomy_cleanup_queryset(
            self.request, _apply_knowledge_filters(self.request, _base_knowledge_queryset())
        )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(taxonomy_cleanup_filter_context(self.request))
        context.update(
            {
                'domains': Domain.objects.order_by('name'),
                'sources': Source.objects.order_by('title'),
                'review_statuses': KnowledgeUnit.ReviewStatus.choices,
                'governance_statuses': KnowledgeUnit.GovernanceStatus.choices,
                'imported_via_choices': KnowledgeUnit.ImportedVia.choices,
                'knowledge_types': KnowledgeUnit.KnowledgeType.choices,
                'value_levels': KnowledgeUnit.ValueLevel.choices,
                'all_tags': Tag.objects.order_by('name'),
                'summary_metrics': get_cleanup_summary_metrics(),
                'uncategorized_domain': get_or_create_uncategorized_domain(),
            }
        )
        return context


class TaxonomyCleanupBulkUpdateView(View):
    def post(self, request):
        next_url = request.POST.get('next_url') or reverse_lazy('knowledge:taxonomy_cleanup')
        selected_ids = request.POST.getlist('unit_ids')
        if not selected_ids:
            messages.warning(request, 'Select at least one knowledge unit.')
            return redirect(next_url)

        queryset = KnowledgeUnit.objects.filter(id__in=selected_ids)
        bulk_action = request.POST.get('bulk_action', '').strip()

        if bulk_action == 'taxonomy_update':
            for msg in apply_taxonomy_cleanup_bulk_update(request, queryset):
                if 'nothing changed' in msg:
                    messages.info(request, msg)
                else:
                    messages.success(request, msg)
        elif bulk_action in QUICK_BULK_ACTIONS:
            _apply_bulk_action(request, queryset, action=QUICK_BULK_ACTIONS[bulk_action])
        else:
            messages.warning(request, 'Unknown action.')

        return redirect(next_url)


class TaxonomyCleanupExportCSVView(View):
    def get(self, request):
        qs = get_taxonomy_cleanup_queryset(
            request, _apply_knowledge_filters(request, _base_knowledge_queryset())
        )
        return export_knowledge_units_csv(qs)


class KnowledgeUnitQuickActionView(View):
    def post(self, request, pk):
        unit = get_object_or_404(KnowledgeUnit, pk=pk)
        action = request.POST.get('action')
        notes = request.POST.get('approval_notes', '').strip()
        now = timezone.now()

        if action == 'mark_reviewed':
            unit.review_status = KnowledgeUnit.ReviewStatus.REVIEWED
            unit.governance_status = KnowledgeUnit.GovernanceStatus.REVIEWED
            unit.reviewed_by = request.user
            unit.reviewed_at = now
            messages.success(request, f'Marked reviewed: {unit.title}')
        elif action == 'approve':
            unit.review_status = KnowledgeUnit.ReviewStatus.APPROVED
            unit.governance_status = KnowledgeUnit.GovernanceStatus.APPROVED
            unit.reviewed_by = request.user
            unit.reviewed_at = now
            messages.success(request, f'Approved: {unit.title}')
        elif action == 'archive':
            unit.review_status = KnowledgeUnit.ReviewStatus.ARCHIVED
            unit.governance_status = KnowledgeUnit.GovernanceStatus.ARCHIVED
            unit.reviewed_by = request.user
            unit.reviewed_at = now
            messages.success(request, f'Archived: {unit.title}')
        elif action == 'mark_duplicate':
            unit.is_duplicate = True
            unit.assign_duplicate_group()
            messages.success(request, f'Marked duplicate: {unit.title}')
        elif action == 'restore_duplicate':
            unit.is_duplicate = False
            unit.duplicate_group = None
            messages.success(request, f'Restored duplicate flag: {unit.title}')
        elif action == 'quick_update':
            confidence = request.POST.get('confidence_level')
            if confidence in dict(KnowledgeUnit.ValueLevel.choices):
                unit.confidence_level = confidence
            tag_id = request.POST.get('tag_id')
            if tag_id:
                tag = Tag.objects.filter(pk=tag_id).first()
                if tag:
                    unit.tags.add(tag)
            messages.success(request, f'Updated quick review fields: {unit.title}')

        if notes:
            unit.approval_notes = notes

        unit.save()
        next_url = request.POST.get('next_url')
        if next_url:
            return redirect(next_url)
        return redirect('knowledge:knowledgeunit_detail', pk=pk)


class KnowledgeRelationshipListView(ListView):
    model = KnowledgeRelationship
    template_name = 'knowledge/relationship_list.html'
    context_object_name = 'relationships'
    paginate_by = 25

    def get_queryset(self):
        qs = KnowledgeRelationship.objects.select_related(
            'from_knowledge_unit', 'to_knowledge_unit'
        )
        relationship_type = self.request.GET.get('relationship_type')
        if relationship_type:
            qs = qs.filter(relationship_type=relationship_type)
        from_unit = self.request.GET.get('from_knowledge_unit')
        if from_unit:
            qs = qs.filter(from_knowledge_unit_id=from_unit)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['relationship_types'] = KnowledgeRelationship.RelationshipType.choices
        context['knowledge_units'] = KnowledgeUnit.objects.order_by('title')
        context['filter_relationship_type'] = self.request.GET.get('relationship_type', '')
        context['filter_from_unit'] = self.request.GET.get('from_knowledge_unit', '')
        return context


class KnowledgeRelationshipDetailView(DetailView):
    model = KnowledgeRelationship
    template_name = 'knowledge/relationship_detail.html'
    context_object_name = 'relationship'

    def get_queryset(self):
        return KnowledgeRelationship.objects.select_related(
            'from_knowledge_unit', 'to_knowledge_unit'
        )


class KnowledgeRelationshipCreateView(CreateView):
    model = KnowledgeRelationship
    form_class = KnowledgeRelationshipForm
    template_name = 'knowledge/relationship_form.html'
    success_url = reverse_lazy('knowledge:relationship_list')

    def get_initial(self):
        initial = super().get_initial()
        from_unit = self.request.GET.get('from_knowledge_unit')
        if from_unit:
            initial['from_knowledge_unit'] = from_unit
        return initial


class KnowledgeRelationshipUpdateView(UpdateView):
    model = KnowledgeRelationship
    form_class = KnowledgeRelationshipForm
    template_name = 'knowledge/relationship_form.html'
    context_object_name = 'relationship'

    def get_success_url(self):
        return reverse_lazy('knowledge:relationship_detail', kwargs={'pk': self.object.pk})


class KnowledgeRelationshipDeleteView(DeleteView):
    model = KnowledgeRelationship
    template_name = 'knowledge/relationship_confirm_delete.html'
    context_object_name = 'relationship'
    success_url = reverse_lazy('knowledge:relationship_list')
