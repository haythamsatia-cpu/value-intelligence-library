from django.urls import path

from . import views

app_name = 'taxonomy'

urlpatterns = [
    path('', views.TaxonomyIndexView.as_view(), name='index'),
    path('domains/', views.DomainListView.as_view(), name='domain_list'),
    path('domains/create/', views.DomainCreateView.as_view(), name='domain_create'),
    path('domains/<uuid:pk>/edit/', views.DomainUpdateView.as_view(), name='domain_update'),
    path('domains/<uuid:pk>/delete/', views.DomainDeleteView.as_view(), name='domain_delete'),
    path('subdomains/', views.SubdomainListView.as_view(), name='subdomain_list'),
    path('subdomains/create/', views.SubdomainCreateView.as_view(), name='subdomain_create'),
    path('subdomains/<uuid:pk>/edit/', views.SubdomainUpdateView.as_view(), name='subdomain_update'),
    path('subdomains/<uuid:pk>/delete/', views.SubdomainDeleteView.as_view(), name='subdomain_delete'),
    path('topics/', views.TopicListView.as_view(), name='topic_list'),
    path('topics/create/', views.TopicCreateView.as_view(), name='topic_create'),
    path('topics/<uuid:pk>/edit/', views.TopicUpdateView.as_view(), name='topic_update'),
    path('topics/<uuid:pk>/delete/', views.TopicDeleteView.as_view(), name='topic_delete'),
    path('concepts/', views.ConceptListView.as_view(), name='concept_list'),
    path('concepts/create/', views.ConceptCreateView.as_view(), name='concept_create'),
    path('concepts/<uuid:pk>/edit/', views.ConceptUpdateView.as_view(), name='concept_update'),
    path('concepts/<uuid:pk>/delete/', views.ConceptDeleteView.as_view(), name='concept_delete'),
    path('tags/', views.TagListView.as_view(), name='tag_list'),
    path('tags/create/', views.TagCreateView.as_view(), name='tag_create'),
    path('tags/<uuid:pk>/edit/', views.TagUpdateView.as_view(), name='tag_update'),
    path('tags/<uuid:pk>/delete/', views.TagDeleteView.as_view(), name='tag_delete'),
]
