from config.csv_export import csv_response

from .models import Chapter, Source


def export_sources_csv():
    header = [
        'id', 'title', 'subtitle', 'source_type', 'authors', 'year', 'edition', 'isbn', 'publisher',
        'total_pages', 'primary_domain', 'priority', 'status',
        'original_file_path', 'source_extension', 'source_file_size',
        'notes', 'created_at', 'updated_at',
    ]
    rows = []
    for source in Source.objects.select_related('primary_domain').prefetch_related('authors'):
        rows.append([
            str(source.pk),
            source.title,
            source.subtitle,
            source.source_type,
            '; '.join(a.name for a in source.authors.all()),
            source.year or '',
            source.edition,
            source.isbn,
            source.publisher,
            source.total_pages or '',
            source.primary_domain.name if source.primary_domain else '',
            source.priority,
            source.status,
            source.original_file_path,
            source.source_extension,
            source.source_file_size or '',
            source.notes,
            source.created_at.isoformat(),
            source.updated_at.isoformat(),
        ])
    return csv_response('sources.csv', rows, header)


def export_chapters_csv(source_id=None, extraction_status=None):
    qs = Chapter.objects.select_related('source').order_by('source__title', 'chapter_number')
    if source_id:
        qs = qs.filter(source_id=source_id)
    if extraction_status:
        qs = qs.filter(extraction_status=extraction_status)

    header = [
        'id', 'source_title', 'chapter_number', 'title', 'start_page', 'end_page',
        'extraction_status', 'summary', 'notes', 'created_at', 'updated_at',
    ]
    rows = [
        [
            str(ch.pk),
            ch.source.title,
            ch.chapter_number,
            ch.title,
            ch.start_page or '',
            ch.end_page or '',
            ch.extraction_status,
            ch.summary,
            ch.notes,
            ch.created_at.isoformat(),
            ch.updated_at.isoformat(),
        ]
        for ch in qs
    ]
    return csv_response('chapters.csv', rows, header)


def export_processing_center_csv(sources, stats_map):
    header = [
        'id',
        'title',
        'source_type',
        'status',
        'priority',
        'primary_domain',
        'processing_status',
        'ingestion_jobs',
        'ingestion_extracted',
        'text_chunks',
        'extraction_batches',
        'parsed_batches',
        'failed_batches',
        'candidates',
        'knowledge_units',
        'approved_units',
        'pending_review',
        'duplicate_suspects',
        'updated_at',
    ]
    rows = []
    for source in sources:
        stats = stats_map.get(str(source.pk))
        d = stats.to_dict() if stats else {}
        rows.append(
            [
                str(source.pk),
                source.title,
                source.source_type,
                source.status,
                source.priority,
                source.primary_domain.name if source.primary_domain else '',
                d.get('processing_status', ''),
                d.get('ingestion_jobs_count', 0),
                d.get('ingestion_extracted_count', 0),
                d.get('text_chunks_count', 0),
                d.get('extraction_batches_count', 0),
                d.get('parsed_batches_count', 0),
                d.get('failed_batches_count', 0),
                d.get('candidate_count', 0),
                d.get('imported_knowledge_units_count', 0),
                d.get('approved_knowledge_units_count', 0),
                d.get('pending_review_units_count', 0),
                d.get('duplicate_suspects_count', 0),
                source.updated_at.isoformat(),
            ]
        )
    return csv_response('processing_center.csv', rows, header)
