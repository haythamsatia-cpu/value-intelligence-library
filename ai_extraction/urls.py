from django.urls import path

from . import ingestion_views, views

app_name = 'ai_extraction'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('prompts/', views.PromptTemplateListView.as_view(), name='prompt_list'),
    path('prompts/create/', views.PromptTemplateCreateView.as_view(), name='prompt_create'),
    path('prompts/<uuid:pk>/', views.PromptTemplateDetailView.as_view(), name='prompt_detail'),
    path('prompts/<uuid:pk>/edit/', views.PromptTemplateUpdateView.as_view(), name='prompt_update'),
    path('prompts/<uuid:pk>/delete/', views.PromptTemplateDeleteView.as_view(), name='prompt_delete'),
    path('prompt-sandbox/', views.PromptSandboxView.as_view(), name='prompt_sandbox'),
    path('batches/', views.BatchListView.as_view(), name='batch_list'),
    path('batches/create/', views.BatchCreateView.as_view(), name='batch_create'),
    path('batches/<uuid:pk>/', views.BatchDetailView.as_view(), name='batch_detail'),
    path('batches/<uuid:pk>/edit/', views.BatchUpdateView.as_view(), name='batch_update'),
    path('batches/<uuid:pk>/delete/', views.BatchDeleteView.as_view(), name='batch_delete'),
    path('batches/<uuid:pk>/ai-output/', views.BatchAiOutputUpdateView.as_view(), name='batch_ai_output'),
    path('batches/<uuid:pk>/parse/', views.BatchParseAiOutputView.as_view(), name='batch_parse'),
    path('batches/<uuid:pk>/fast-import/', views.BatchFastImportView.as_view(), name='batch_fast_import'),
    path('candidates/', views.CandidateListView.as_view(), name='candidate_list'),
    path('candidates/bulk-import/', views.CandidateBulkImportView.as_view(), name='candidate_bulk_import'),
    path('candidates/bulk-reject/', views.CandidateBulkRejectView.as_view(), name='candidate_bulk_reject'),
    path('candidates/create/', views.CandidateCreateView.as_view(), name='candidate_create'),
    path('candidates/<uuid:pk>/', views.CandidateDetailView.as_view(), name='candidate_detail'),
    path('candidates/<uuid:pk>/edit/', views.CandidateUpdateView.as_view(), name='candidate_update'),
    path('candidates/<uuid:pk>/import/', views.CandidateImportView.as_view(), name='candidate_import'),
    path('candidates/<uuid:pk>/reject/', views.CandidateRejectView.as_view(), name='candidate_reject'),
    path('ingestion/', ingestion_views.IngestionJobListView.as_view(), name='ingestion_list'),
    path('ingestion/create/', ingestion_views.IngestionJobCreateView.as_view(), name='ingestion_create'),
    path('ingestion/<uuid:pk>/', ingestion_views.IngestionJobDetailView.as_view(), name='ingestion_detail'),
    path('ingestion/<uuid:pk>/delete/', ingestion_views.IngestionJobDeleteView.as_view(), name='ingestion_delete'),
    path('ingestion/<uuid:pk>/extract/', ingestion_views.IngestionExtractTextView.as_view(), name='ingestion_extract'),
    path('ingestion/<uuid:pk>/manual-text/', ingestion_views.IngestionSaveManualTextView.as_view(), name='ingestion_manual_text'),
    path('ingestion/<uuid:pk>/create-chunks/', ingestion_views.IngestionCreateChunksView.as_view(), name='ingestion_create_chunks'),
    path('ingestion/<uuid:pk>/bulk-batches/', ingestion_views.IngestionBulkBatchesView.as_view(), name='ingestion_bulk_batches'),
    path(
        'ingestion/<uuid:pk>/bulk-fast-import/',
        ingestion_views.IngestionBulkFastImportView.as_view(),
        name='ingestion_bulk_fast_import',
    ),
    path('chunks/', ingestion_views.TextChunkListView.as_view(), name='chunk_list'),
    path('chunks/<uuid:pk>/', ingestion_views.TextChunkDetailView.as_view(), name='chunk_detail'),
    path('chunks/<uuid:pk>/create-batch/', ingestion_views.TextChunkCreateBatchView.as_view(), name='chunk_create_batch'),
]
