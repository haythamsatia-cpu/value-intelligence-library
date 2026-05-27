from django.db.models import Q
from django.views.generic import ListView, TemplateView

from knowledge.models import KnowledgeUnit
from library.models import Chapter, Source


class DashboardView(TemplateView):
    template_name = 'dashboard/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_sources'] = Source.objects.count()
        context['total_chapters'] = Chapter.objects.count()
        context['total_knowledge_units'] = KnowledgeUnit.objects.count()
        context['approved_knowledge_units'] = KnowledgeUnit.objects.filter(
            review_status=KnowledgeUnit.ReviewStatus.APPROVED
        ).count()
        context['draft_knowledge_units'] = KnowledgeUnit.objects.filter(
            review_status=KnowledgeUnit.ReviewStatus.DRAFT
        ).count()
        context['sources_in_progress'] = Source.objects.filter(
            status=Source.Status.IN_PROGRESS
        ).count()
        context['fast_imported_units'] = KnowledgeUnit.objects.filter(
            imported_via=KnowledgeUnit.ImportedVia.FAST_IMPORT
        ).count()
        context['candidate_reviewed_units'] = KnowledgeUnit.objects.filter(
            imported_via=KnowledgeUnit.ImportedVia.CANDIDATE_REVIEW
        ).count()
        context['pending_review_units'] = KnowledgeUnit.objects.filter(
            governance_status=KnowledgeUnit.GovernanceStatus.PENDING_REVIEW
        ).count()
        return context


class SearchView(ListView):
    model = KnowledgeUnit
    template_name = 'dashboard/search.html'
    context_object_name = 'results'
    paginate_by = 25

    def get_queryset(self):
        qs = KnowledgeUnit.objects.select_related(
            'domain', 'source', 'chapter'
        ).prefetch_related('tags')
        query = self.request.GET.get('q', '').strip()
        if not query:
            return qs.none()
        qs = qs.filter(
            Q(title__icontains=query)
            | Q(executive_insight__icontains=query)
            | Q(detailed_explanation__icontains=query)
            | Q(practical_application__icontains=query)
            | Q(consultant_use_case__icontains=query)
            | Q(course_use_case__icontains=query)
            | Q(keywords__icontains=query)
            | Q(citation__icontains=query)
            | Q(personal_commentary__icontains=query)
            | Q(approval_notes__icontains=query)
        )
        ordering = self.request.GET.get('ordering', '-updated_at')
        ordering_map = {
            '-updated_at': '-updated_at',
            '-created_at': '-created_at',
            'title': 'title',
            'consulting_value': 'consulting_value',
            'teaching_value': 'teaching_value',
        }
        return qs.order_by(ordering_map.get(ordering, '-updated_at'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '').strip()
        context['ordering'] = self.request.GET.get('ordering', '-updated_at')
        context['view_mode'] = self.request.GET.get('view', 'table')
        return context
