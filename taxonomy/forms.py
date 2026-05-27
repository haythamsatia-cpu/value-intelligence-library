from django import forms

from config.forms import BootstrapFormMixin

from .models import Concept, Domain, Subdomain, Tag, Topic


class DomainForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Domain
        fields = ['name', 'description']
        widgets = {'description': forms.Textarea(attrs={'rows': 4})}


class SubdomainForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Subdomain
        fields = ['domain', 'name', 'description']
        widgets = {'description': forms.Textarea(attrs={'rows': 4})}


class TopicForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Topic
        fields = ['subdomain', 'name', 'description']
        widgets = {'description': forms.Textarea(attrs={'rows': 4})}


class ConceptForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Concept
        fields = ['topic', 'name', 'description']
        widgets = {'description': forms.Textarea(attrs={'rows': 4})}


class TagForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Tag
        fields = ['name']
