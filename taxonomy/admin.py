from django.contrib import admin

from .models import Concept, Domain, Subdomain, Tag, Topic


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'updated_at')
    search_fields = ('name', 'description')
    ordering = ('name',)


@admin.register(Subdomain)
class SubdomainAdmin(admin.ModelAdmin):
    list_display = ('name', 'domain', 'created_at', 'updated_at')
    list_filter = ('domain',)
    search_fields = ('name', 'description', 'domain__name')
    ordering = ('domain__name', 'name')
    autocomplete_fields = ('domain',)


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'subdomain', 'created_at', 'updated_at')
    list_filter = ('subdomain__domain', 'subdomain')
    search_fields = ('name', 'description', 'subdomain__name')
    ordering = ('subdomain__domain__name', 'subdomain__name', 'name')
    autocomplete_fields = ('subdomain',)


@admin.register(Concept)
class ConceptAdmin(admin.ModelAdmin):
    list_display = ('name', 'topic', 'created_at', 'updated_at')
    list_filter = ('topic__subdomain__domain', 'topic__subdomain')
    search_fields = ('name', 'description', 'topic__name')
    ordering = ('topic__subdomain__domain__name', 'topic__name', 'name')
    autocomplete_fields = ('topic',)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)
    ordering = ('name',)
