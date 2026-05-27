from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from .forms import ConceptForm, DomainForm, SubdomainForm, TagForm, TopicForm
from .models import Concept, Domain, Subdomain, Tag, Topic


class DomainListView(ListView):
    model = Domain
    template_name = 'taxonomy/domain_list.html'
    context_object_name = 'items'


class DomainCreateView(CreateView):
    model = Domain
    form_class = DomainForm
    template_name = 'taxonomy/domain_form.html'
    success_url = reverse_lazy('taxonomy:domain_list')


class DomainUpdateView(UpdateView):
    model = Domain
    form_class = DomainForm
    template_name = 'taxonomy/domain_form.html'
    success_url = reverse_lazy('taxonomy:domain_list')


class DomainDeleteView(DeleteView):
    model = Domain
    template_name = 'taxonomy/confirm_delete.html'
    success_url = reverse_lazy('taxonomy:domain_list')
    extra_context = {'entity_name': 'Domain'}


class SubdomainListView(ListView):
    model = Subdomain
    template_name = 'taxonomy/subdomain_list.html'
    context_object_name = 'items'

    def get_queryset(self):
        return Subdomain.objects.select_related('domain')


class SubdomainCreateView(CreateView):
    model = Subdomain
    form_class = SubdomainForm
    template_name = 'taxonomy/subdomain_form.html'
    success_url = reverse_lazy('taxonomy:subdomain_list')


class SubdomainUpdateView(UpdateView):
    model = Subdomain
    form_class = SubdomainForm
    template_name = 'taxonomy/subdomain_form.html'
    success_url = reverse_lazy('taxonomy:subdomain_list')


class SubdomainDeleteView(DeleteView):
    model = Subdomain
    template_name = 'taxonomy/confirm_delete.html'
    success_url = reverse_lazy('taxonomy:subdomain_list')
    extra_context = {'entity_name': 'Subdomain'}


class TopicListView(ListView):
    model = Topic
    template_name = 'taxonomy/topic_list.html'
    context_object_name = 'items'

    def get_queryset(self):
        return Topic.objects.select_related('subdomain', 'subdomain__domain')


class TopicCreateView(CreateView):
    model = Topic
    form_class = TopicForm
    template_name = 'taxonomy/topic_form.html'
    success_url = reverse_lazy('taxonomy:topic_list')


class TopicUpdateView(UpdateView):
    model = Topic
    form_class = TopicForm
    template_name = 'taxonomy/topic_form.html'
    success_url = reverse_lazy('taxonomy:topic_list')


class TopicDeleteView(DeleteView):
    model = Topic
    template_name = 'taxonomy/confirm_delete.html'
    success_url = reverse_lazy('taxonomy:topic_list')
    extra_context = {'entity_name': 'Topic'}


class ConceptListView(ListView):
    model = Concept
    template_name = 'taxonomy/concept_list.html'
    context_object_name = 'items'

    def get_queryset(self):
        return Concept.objects.select_related('topic', 'topic__subdomain', 'topic__subdomain__domain')


class ConceptCreateView(CreateView):
    model = Concept
    form_class = ConceptForm
    template_name = 'taxonomy/concept_form.html'
    success_url = reverse_lazy('taxonomy:concept_list')


class ConceptUpdateView(UpdateView):
    model = Concept
    form_class = ConceptForm
    template_name = 'taxonomy/concept_form.html'
    success_url = reverse_lazy('taxonomy:concept_list')


class ConceptDeleteView(DeleteView):
    model = Concept
    template_name = 'taxonomy/confirm_delete.html'
    success_url = reverse_lazy('taxonomy:concept_list')
    extra_context = {'entity_name': 'Concept'}


class TagListView(ListView):
    model = Tag
    template_name = 'taxonomy/tag_list.html'
    context_object_name = 'items'


class TagCreateView(CreateView):
    model = Tag
    form_class = TagForm
    template_name = 'taxonomy/tag_form.html'
    success_url = reverse_lazy('taxonomy:tag_list')


class TagUpdateView(UpdateView):
    model = Tag
    form_class = TagForm
    template_name = 'taxonomy/tag_form.html'
    success_url = reverse_lazy('taxonomy:tag_list')


class TagDeleteView(DeleteView):
    model = Tag
    template_name = 'taxonomy/confirm_delete.html'
    success_url = reverse_lazy('taxonomy:tag_list')
    extra_context = {'entity_name': 'Tag'}


class TaxonomyIndexView(TemplateView):
    """Taxonomy landing page with links to all taxonomy managers."""
    template_name = 'taxonomy/index.html'
