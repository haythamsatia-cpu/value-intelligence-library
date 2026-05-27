from django.urls import path

from . import bulk_import_views, views

app_name = 'library'

urlpatterns = [
    path('bulk-import/', bulk_import_views.BulkImportCenterView.as_view(), name='bulk_import'),
    path(
        'bulk-import/template.csv',
        bulk_import_views.BulkImportCsvTemplateView.as_view(),
        name='bulk_import_template',
    ),
    path('bulk-import/csv/', bulk_import_views.BulkImportCsvUploadView.as_view(), name='bulk_import_csv'),
    path(
        'bulk-import/folder-scan/',
        bulk_import_views.BulkImportFolderScanView.as_view(),
        name='bulk_import_folder_scan',
    ),
    path('bulk-import/preview/', bulk_import_views.BulkImportPreviewView.as_view(), name='bulk_import_preview'),
    path(
        'bulk-import/preview/bulk-edit/',
        bulk_import_views.BulkImportApplyBulkEditsView.as_view(),
        name='bulk_import_bulk_edit',
    ),
    path('bulk-import/commit/', bulk_import_views.BulkImportCommitView.as_view(), name='bulk_import_commit'),
    path('sources/bulk-update/', bulk_import_views.SourceBulkUpdateView.as_view(), name='source_bulk_update'),
    path('processing-center/', views.ProcessingCenterListView.as_view(), name='processing_center'),
    path(
        'processing-center/export.csv',
        views.ProcessingCenterExportCSVView.as_view(),
        name='processing_center_export_csv',
    ),
    path('sources/', views.SourceListView.as_view(), name='source_list'),
    path('sources/export.csv', views.SourceExportCSVView.as_view(), name='source_export_csv'),
    path('sources/create/', views.SourceCreateView.as_view(), name='source_create'),
    path('sources/<uuid:pk>/', views.SourceDetailView.as_view(), name='source_detail'),
    path('sources/<uuid:pk>/edit/', views.SourceUpdateView.as_view(), name='source_update'),
    path('sources/<uuid:pk>/delete/', views.SourceDeleteView.as_view(), name='source_delete'),
    path('chapters/', views.ChapterListView.as_view(), name='chapter_list'),
    path('chapters/export.csv', views.ChapterExportCSVView.as_view(), name='chapter_export_csv'),
    path('chapters/create/', views.ChapterCreateView.as_view(), name='chapter_create'),
    path('chapters/<uuid:pk>/', views.ChapterDetailView.as_view(), name='chapter_detail'),
    path('chapters/<uuid:pk>/edit/', views.ChapterUpdateView.as_view(), name='chapter_update'),
    path('chapters/<uuid:pk>/delete/', views.ChapterDeleteView.as_view(), name='chapter_delete'),
    path('authors/', views.AuthorListView.as_view(), name='author_list'),
    path('authors/create/', views.AuthorCreateView.as_view(), name='author_create'),
    path('authors/<uuid:pk>/', views.AuthorDetailView.as_view(), name='author_detail'),
    path('authors/<uuid:pk>/edit/', views.AuthorUpdateView.as_view(), name='author_update'),
    path('authors/<uuid:pk>/delete/', views.AuthorDeleteView.as_view(), name='author_delete'),
]
