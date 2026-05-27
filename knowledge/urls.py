from django.urls import path

from . import views

app_name = 'knowledge'

urlpatterns = [
    path('units/', views.KnowledgeUnitListView.as_view(), name='knowledgeunit_list'),
    path('review-queue/', views.KnowledgeReviewQueueView.as_view(), name='review_queue'),
    path('taxonomy-cleanup/', views.TaxonomyCleanupListView.as_view(), name='taxonomy_cleanup'),
    path(
        'taxonomy-cleanup/export.csv',
        views.TaxonomyCleanupExportCSVView.as_view(),
        name='taxonomy_cleanup_export_csv',
    ),
    path(
        'taxonomy-cleanup/bulk-update/',
        views.TaxonomyCleanupBulkUpdateView.as_view(),
        name='taxonomy_cleanup_bulk_update',
    ),
    path('units/export.csv', views.KnowledgeUnitExportCSVView.as_view(), name='knowledgeunit_export_csv'),
    path('units/bulk-action/', views.KnowledgeUnitBulkActionView.as_view(), name='knowledgeunit_bulk_action'),
    path('units/create/', views.KnowledgeUnitCreateView.as_view(), name='knowledgeunit_create'),
    path('units/<uuid:pk>/', views.KnowledgeUnitDetailView.as_view(), name='knowledgeunit_detail'),
    path('units/<uuid:pk>/quick-action/', views.KnowledgeUnitQuickActionView.as_view(), name='knowledgeunit_quick_action'),
    path('units/<uuid:pk>/edit/', views.KnowledgeUnitUpdateView.as_view(), name='knowledgeunit_update'),
    path('units/<uuid:pk>/delete/', views.KnowledgeUnitDeleteView.as_view(), name='knowledgeunit_delete'),
    path('relationships/', views.KnowledgeRelationshipListView.as_view(), name='relationship_list'),
    path('relationships/create/', views.KnowledgeRelationshipCreateView.as_view(), name='relationship_create'),
    path('relationships/<uuid:pk>/', views.KnowledgeRelationshipDetailView.as_view(), name='relationship_detail'),
    path('relationships/<uuid:pk>/edit/', views.KnowledgeRelationshipUpdateView.as_view(), name='relationship_update'),
    path('relationships/<uuid:pk>/delete/', views.KnowledgeRelationshipDeleteView.as_view(), name='relationship_delete'),
]
