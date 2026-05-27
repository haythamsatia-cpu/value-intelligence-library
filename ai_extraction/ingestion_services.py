"""
Document ingestion: PDF text extraction, chunking, and extraction batch creation.
No external AI API calls.
"""
from dataclasses import dataclass, field

from django.db import transaction

from .models import DocumentIngestionJob, ExtractionBatch, ExtractionPromptTemplate, TextChunk

DEFAULT_CHUNK_SIZE = 12000
MIN_MEANINGFUL_CHARS_PER_PAGE = 30


@dataclass
class ExtractionResult:
    success: bool
    message: str
    page_count: int = 0
    char_count: int = 0


@dataclass
class ChunkingResult:
    created: int = 0
    message: str = ''


@dataclass
class BulkBatchResult:
    created: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def extract_pdf_text(job: DocumentIngestionJob) -> ExtractionResult:
    """Extract text from a PDF using pypdf. Updates job in place."""
    if job.extraction_method != DocumentIngestionJob.ExtractionMethod.PYPDF:
        return ExtractionResult(False, 'Extraction method is not PDF (pypdf).')

    if not job.file:
        return ExtractionResult(False, 'No file uploaded for this ingestion job.')

    if not job.is_pdf:
        return ExtractionResult(
            False,
            'File is not a PDF. Use Manual text method or upload a .pdf file.',
        )

    job.status = DocumentIngestionJob.Status.EXTRACTING
    job.error_message = ''
    job.save(update_fields=['status', 'error_message', 'updated_at'])

    try:
        from pypdf import PdfReader

        reader = PdfReader(job.file.path)
        page_count = len(reader.pages)
        if page_count == 0:
            job.status = DocumentIngestionJob.Status.FAILED
            job.error_message = 'PDF has no pages.'
            job.save(update_fields=['status', 'error_message', 'updated_at'])
            return ExtractionResult(False, job.error_message)

        parts = []
        non_empty_pages = 0
        for index, page in enumerate(reader.pages, start=1):
            page_text = (page.extract_text() or '').strip()
            if page_text:
                non_empty_pages += 1
                parts.append(f'--- Page {index} ---\n{page_text}')

        full_text = '\n\n'.join(parts).strip()
        char_count = len(full_text)

        if char_count == 0 or non_empty_pages == 0:
            job.status = DocumentIngestionJob.Status.FAILED
            job.error_message = (
                'No extractable text found. This PDF may be scanned or image-only. '
                'OCR is not available in this phase — use Manual text and paste content, '
                'or use a text-based PDF.'
            )
            job.extracted_text = ''
            job.save(update_fields=['status', 'error_message', 'extracted_text', 'updated_at'])
            return ExtractionResult(False, job.error_message, page_count=page_count)

        if non_empty_pages < page_count * 0.2 and char_count < page_count * MIN_MEANINGFUL_CHARS_PER_PAGE:
            job.status = DocumentIngestionJob.Status.FAILED
            job.error_message = (
                f'Very little text extracted ({char_count} chars from {page_count} pages). '
                'The PDF may be mostly scanned images. OCR is planned for a future phase.'
            )
            job.extracted_text = full_text
            job.save(update_fields=['status', 'error_message', 'extracted_text', 'updated_at'])
            return ExtractionResult(False, job.error_message, page_count=page_count, char_count=char_count)

        job.extracted_text = full_text
        job.status = DocumentIngestionJob.Status.EXTRACTED
        job.error_message = ''
        job.save(update_fields=['extracted_text', 'status', 'error_message', 'updated_at'])
        return ExtractionResult(
            True,
            f'Extracted text from {page_count} page(s) ({char_count:,} characters).',
            page_count=page_count,
            char_count=char_count,
        )

    except Exception as exc:
        job.status = DocumentIngestionJob.Status.FAILED
        job.error_message = f'PDF extraction failed: {exc}'
        job.save(update_fields=['status', 'error_message', 'updated_at'])
        return ExtractionResult(False, job.error_message)


def _parse_page_markers(text: str) -> list[tuple[int | None, str]]:
    """Split extracted text into (page_number, content) segments."""
    segments = []
    current_page = None
    current_lines = []

    for line in text.split('\n'):
        stripped = line.strip()
        if stripped.startswith('--- Page ') and stripped.endswith('---'):
            if current_lines:
                segments.append((current_page, '\n'.join(current_lines).strip()))
                current_lines = []
            try:
                page_num = int(stripped.replace('--- Page ', '').replace(' ---', ''))
                current_page = page_num
            except ValueError:
                current_page = None
        else:
            current_lines.append(line)

    if current_lines:
        segments.append((current_page, '\n'.join(current_lines).strip()))

    if not segments:
        return [(None, text)]
    return segments


@transaction.atomic
def create_text_chunks(job: DocumentIngestionJob, chunk_size: int = DEFAULT_CHUNK_SIZE) -> ChunkingResult:
    """Create TextChunk rows from job.extracted_text. Replaces existing chunks for this job."""
    text = job.extracted_text.strip()
    if not text:
        return ChunkingResult(0, 'No extracted text. Run PDF extraction or paste manual text first.')

    job.chunks.all().delete()

    segments = _parse_page_markers(text)
    pieces = [(p, s) for p, s in segments if s.strip()]
    if not pieces:
        pieces = [(None, text)]

    source_title = job.source.title[:200]
    chunk_number = 0
    buffer = ''
    start_page = None
    end_page = None

    def flush_buffer():
        nonlocal chunk_number, buffer, start_page, end_page
        if not buffer.strip():
            return
        chunk_number += 1
        if start_page and end_page:
            page_label = (
                f'Pages {start_page}'
                if start_page == end_page
                else f'Pages {start_page}–{end_page}'
            )
            title = f'{source_title} — {page_label}'
        else:
            title = f'{source_title} — Chunk {chunk_number}'
        TextChunk.objects.create(
            ingestion_job=job,
            source=job.source,
            title=title[:500],
            chunk_number=chunk_number,
            start_page=start_page,
            end_page=end_page,
            text=buffer.strip(),
        )
        buffer = ''
        start_page = None
        end_page = None

    for page_num, segment_text in pieces:
        content = f'[Page {page_num}]\n{segment_text}' if page_num else segment_text
        while content:
            space = chunk_size - len(buffer) - (2 if buffer else 0)
            if space <= 0:
                flush_buffer()
                space = chunk_size
            if len(content) <= space:
                if buffer:
                    buffer += '\n\n' + content
                else:
                    buffer = content
                    start_page = page_num
                end_page = page_num
                content = ''
            else:
                cut = content[:space]
                newline = cut.rfind('\n')
                if newline > space // 2:
                    cut = content[:newline]
                    rest = content[newline:].lstrip('\n')
                else:
                    rest = content[space:]
                if buffer:
                    buffer += '\n\n' + cut
                else:
                    buffer = cut
                    start_page = page_num
                end_page = page_num
                flush_buffer()
                content = rest

    flush_buffer()

    if chunk_number == 0:
        return ChunkingResult(0, 'No chunks could be created from the extracted text.')

    return ChunkingResult(
        chunk_number,
        f'Created {chunk_number} text chunk(s) (~{chunk_size:,} characters each).',
    )


@transaction.atomic
def create_batch_from_chunk(
    chunk: TextChunk,
    prompt_template: ExtractionPromptTemplate,
    *,
    batch_status: str = ExtractionBatch.Status.READY_FOR_AI,
) -> ExtractionBatch:
    """Create an ExtractionBatch from a text chunk and link it."""
    if chunk.created_batch_id:
        return chunk.created_batch

    batch = ExtractionBatch.objects.create(
        source=chunk.source,
        chapter=chunk.chapter,
        title=chunk.title[:500],
        input_text=chunk.text,
        prompt_template=prompt_template,
        status=batch_status,
        notes=f'Auto-created from ingestion chunk #{chunk.chunk_number}.',
    )
    chunk.created_batch = batch
    chunk.save(update_fields=['created_batch', 'updated_at'])
    return batch


@transaction.atomic
def bulk_create_batches_from_job(
    job: DocumentIngestionJob,
    prompt_template: ExtractionPromptTemplate,
) -> BulkBatchResult:
    """Create extraction batches for all chunks without an existing batch."""
    result = BulkBatchResult()
    for chunk in job.chunks.filter(created_batch__isnull=True).order_by('chunk_number'):
        try:
            create_batch_from_chunk(chunk, prompt_template)
            result.created += 1
        except Exception as exc:
            result.errors.append(f'Chunk {chunk.chunk_number}: {exc}')
    result.skipped = job.chunks.filter(created_batch__isnull=False).count()
    return result
