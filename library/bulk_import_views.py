import json

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView

from taxonomy.models import Domain

from .bulk_import import (
    csv_template_content,
    delete_staging,
    import_preview_rows,
    load_staging,
    new_staging_id,
    parse_csv_upload,
    preview_stats,
    rows_from_staging_dict,
    rows_to_staging_dict,
    save_staging,
    scan_folder,
)
from .forms import BulkFolderScanForm, BulkImportCsvUploadForm, BulkImportOptionsForm
from .models import Source


class BulkImportCenterView(TemplateView):
    template_name = 'library/bulk_import_center.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['import_summary'] = self.request.session.pop('bulk_import_summary', None)
        context['csv_form'] = BulkImportCsvUploadForm()
        context['folder_form'] = BulkFolderScanForm()
        return context


class BulkImportCsvTemplateView(View):
    def get(self, request):
        response = HttpResponse(csv_template_content(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="source_bulk_import_template.csv"'
        return response


class BulkImportCsvUploadView(View):
    """Upload CSV → staging preview."""

    def post(self, request):
        form = BulkImportCsvUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, 'Select a valid CSV file.')
            return redirect('library:bulk_import')

        rows, errors = parse_csv_upload(form.cleaned_data['csv_file'])
        for err in errors:
            messages.warning(request, err)
        if not rows:
            return redirect('library:bulk_import')

        staging_id = new_staging_id()
        save_staging(
            staging_id,
            {
                'kind': 'csv',
                'rows': rows_to_staging_dict(rows),
                'scan_root': '',
            },
        )
        request.session['bulk_import_staging_id'] = staging_id
        messages.success(request, f'CSV parsed: {len(rows)} row(s) ready for preview.')
        return redirect('library:bulk_import_preview')


class BulkImportFolderScanView(View):
    def post(self, request):
        form = BulkFolderScanForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Enter a valid folder path.')
            return redirect('library:bulk_import')

        rows, errors = scan_folder(form.cleaned_data['folder_path'])
        for err in errors:
            messages.warning(request, err)
        if not rows:
            return redirect('library:bulk_import')

        staging_id = new_staging_id()
        save_staging(
            staging_id,
            {
                'kind': 'folder',
                'rows': rows_to_staging_dict(rows),
                'scan_root': form.cleaned_data['folder_path'],
            },
        )
        request.session['bulk_import_staging_id'] = staging_id
        messages.success(
            request,
            f'Discovered {len(rows)} file(s). Review and import selected sources.',
        )
        return redirect('library:bulk_import_preview')


class BulkImportPreviewView(TemplateView):
    template_name = 'library/bulk_import_preview.html'
    paginate_by = 100

    def get_staging_payload(self):
        staging_id = self.request.session.get('bulk_import_staging_id')
        if not staging_id:
            return None
        return load_staging(staging_id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payload = self.get_staging_payload()
        if not payload:
            context['missing_staging'] = True
            return context

        rows = rows_from_staging_dict(payload.get('rows', []))
        page = int(self.request.GET.get('page', 1))
        per_page = self.paginate_by
        start = (page - 1) * per_page
        end = start + per_page
        page_rows = rows[start:end]

        context.update(
            {
                'kind': payload.get('kind', 'csv'),
                'scan_root': payload.get('scan_root', ''),
                'all_rows_count': len(rows),
                'preview_rows': page_rows,
                'stats': preview_stats(rows),
                'options_form': BulkImportOptionsForm(),
                'domains': Domain.objects.order_by('name'),
                'page': page,
                'num_pages': max(1, (len(rows) + per_page - 1) // per_page),
                'has_prev': page > 1,
                'has_next': end < len(rows),
                'prev_page': page - 1,
                'next_page': page + 1,
            }
        )
        last_summary = self.request.session.pop('bulk_import_summary', None)
        if last_summary:
            context['import_summary'] = last_summary
        return context


class BulkImportApplyBulkEditsView(View):
    """Apply domain/priority/status/tags to selected row indices on current staging."""

    def post(self, request):
        payload = load_staging(request.session.get('bulk_import_staging_id', ''))
        if not payload:
            messages.error(request, 'Import preview expired. Upload or scan again.')
            return redirect('library:bulk_import')

        rows = rows_from_staging_dict(payload['rows'])
        selected_indices = {int(i) for i in request.POST.getlist('row_index')}
        domain_id = request.POST.get('bulk_domain', '').strip()
        priority = request.POST.get('bulk_priority', '').strip()
        status = request.POST.get('bulk_status', '').strip()
        tag_names = [t.strip() for t in request.POST.get('bulk_tags', '').split(',') if t.strip()]

        domain = Domain.objects.filter(pk=domain_id).first() if domain_id else None

        for row in rows:
            if row.row_index not in selected_indices:
                continue
            if domain:
                row.domain_resolved = str(domain.pk)
                row.domain_unmatched = False
                row.primary_domain_name = domain.name
            if priority in dict(Source.Priority.choices):
                row.priority = priority
            if status in dict(Source.Status.choices):
                row.status = status
            if tag_names:
                row.tags = list(dict.fromkeys(row.tags + tag_names))

        payload['rows'] = rows_to_staging_dict(rows)
        save_staging(request.session['bulk_import_staging_id'], payload)
        messages.success(request, f'Updated {len(selected_indices)} preview row(s).')
        return redirect('library:bulk_import_preview')


class BulkImportCommitView(View):
    def post(self, request):
        staging_id = request.session.get('bulk_import_staging_id')
        payload = load_staging(staging_id) if staging_id else None
        if not payload:
            messages.error(request, 'Import preview expired.')
            return redirect('library:bulk_import')

        rows = rows_from_staging_dict(payload['rows'])
        import_mode = request.POST.get('import_mode', 'all_non_duplicate')
        posted_selected = {int(i) for i in request.POST.getlist('import_row')}
        skip_dup = request.POST.get('skip_duplicates', 'on') == 'on'

        for row in rows:
            if import_mode == 'page_selected':
                row.selected = row.row_index in posted_selected
            else:
                row.selected = not (row.duplicate and skip_dup)

        options_form = BulkImportOptionsForm(request.POST)
        default_domain = None
        if options_form.is_valid() and options_form.cleaned_data.get('default_domain'):
            default_domain = options_form.cleaned_data['default_domain']

        summary = import_preview_rows(
            rows,
            default_domain_id=str(default_domain.pk) if default_domain else None,
            skip_duplicates=skip_dup,
        )
        if payload.get('kind') == 'folder':
            summary.scanned_files_count = len(rows)

        request.session['bulk_import_summary'] = summary.to_dict()
        delete_staging(staging_id)
        request.session.pop('bulk_import_staging_id', None)

        messages.success(
            request,
            f'Import complete: {summary.total_imported} source(s) created.',
        )
        if summary.skipped_duplicates:
            messages.info(request, f'Skipped {summary.skipped_duplicates} duplicate(s).')
        if summary.unmatched_domains:
            messages.warning(
                request,
                f'{summary.unmatched_domains} row(s) used Uncategorized domain.',
            )
        for err in summary.errors[:5]:
            messages.warning(request, err)

        return redirect('library:bulk_import')


class SourceBulkUpdateView(View):
    """Bulk status/domain updates from source library list."""

    def post(self, request):
        ids = request.POST.getlist('source_ids')
        if not ids:
            messages.warning(request, 'Select at least one source.')
            return redirect('library:source_list')

        qs = Source.objects.filter(pk__in=ids)
        domain_id = request.POST.get('bulk_domain', '').strip()
        priority = request.POST.get('bulk_priority', '').strip()
        status = request.POST.get('bulk_status', '').strip()

        changes = []
        if domain_id:
            qs.update(primary_domain_id=domain_id)
            changes.append('domain')
        if priority in dict(Source.Priority.choices):
            qs.update(priority=priority)
            changes.append('priority')
        if status in dict(Source.Status.choices):
            qs.update(status=status)
            changes.append('status')
        if changes:
            messages.success(request, f'Updated {", ".join(changes)} for {len(ids)} source(s).')
        else:
            messages.info(request, 'No bulk fields selected.')
        return redirect(request.POST.get('next_url', reverse_lazy('library:source_list')))
