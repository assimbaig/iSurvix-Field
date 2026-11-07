"""Actor-private export queue and downloads. Enqueuing never performs extraction."""
from io import BytesIO
from pathlib import Path
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import FileResponse,Http404,HttpResponse,JsonResponse
from django.shortcuts import get_object_or_404,redirect,render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET,require_POST,require_http_methods
from django.contrib import messages
from django.utils import timezone
from openpyxl import Workbook
from .export_models import DataExportJob
from .export_forms import DataExportForm
from . import export_service as exports

def _private(response):
 response['Cache-Control']='private, no-store'
 response['X-Content-Type-Options']='nosniff'
 return response

@login_required(login_url='/login/')
@never_cache
@require_http_methods(['GET','POST'])
def index(request):
 initial={}
 if request.GET.get('section') in exports.catalog(request.user):initial['section']=request.GET['section']
 form=DataExportForm(request.POST if request.method=='POST' else None,actor=request.user,initial=initial)
 status=200
 if request.method=='POST':
  status=400
  if set(request.POST)-set(form.fields)-{'csrfmiddlewaretoken'}:return _private(HttpResponse('Only displayed export parameters may be supplied.',status=400))
  if form.is_valid():
   try:job,created=exports.request_export(request.user,form.cleaned_data['section'],project_id=form.cleaned_data['project'].pk if form.cleaned_data['project'] else None,request_key=form.cleaned_data['request_key'])
   except ValidationError as error:form.add_error(None,error)
   else:
    if created:messages.success(request,'Export queued. You can continue working; the background export worker will prepare it.')
    else:messages.info(request,'Existing export: '+job.display_status+'. No duplicate request was created.')
    return redirect('data_exports')
 jobs=DataExportJob.objects.filter(owner=request.user)
 return _private(render(request,'exports/index.html',{'active_view':'data_exports','form':form,'jobs':Paginator(jobs,25).get_page(request.GET.get('page')),'export_catalog':exports.catalog(request.user),'has_active_exports':jobs.filter(status__in=['queued','running'],expires_at__gt=timezone.now()).exists()},status=status))

@login_required(login_url='/login/')
@never_cache
@require_GET
def progress(request):
 exports._actor(request.user)
 jobs=DataExportJob.objects.filter(owner=request.user).order_by('-created_at')[:50]
 from django.utils import timezone
 return _private(JsonResponse({'jobs':[{'id':str(j.pk),'status':j.status if j.expires_at>timezone.now() else 'expired','label':j.get_status_display() if j.expires_at>timezone.now() else 'Expired','rows':j.row_count if j.status=='ready' else None,'error':j.error,'file_name':j.file_name,'prepared_at':timezone.localtime(j.completed_at).strftime('%Y-%m-%d %H:%M:%S %Z') if j.completed_at else ''} for j in jobs]}))

@login_required(login_url='/login/')
@never_cache
@require_POST
def retry(request,job_id):
 job=get_object_or_404(DataExportJob,pk=job_id,owner=request.user)
 try:exports.retry(request.user,job)
 except ValidationError as error:
  return _private(HttpResponse('; '.join(error.messages),status=409,content_type='text/plain'))
 messages.success(request,'Export queued for retry.');return redirect('data_exports')

@login_required(login_url='/login/')
@never_cache
@require_GET
def download(request,job_id):
 job=get_object_or_404(DataExportJob,pk=job_id,owner=request.user)
 try:path=exports.download_authorized(request.user,job)
 except ValidationError as error:return _private(HttpResponse('; '.join(error.messages),status=409,content_type='text/plain'))
 return _private(FileResponse(path.open('rb'),as_attachment=True,filename=job.file_name,content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'))

@login_required(login_url='/login/')
@never_cache
@require_GET
def template(request,section):
 if section not in exports.catalog(request.user):raise Http404()
 book=Workbook(write_only=True);sheet=book.create_sheet('Data');sheet.append(exports.HEADERS[section])
 columns=book.create_sheet('Columns');columns.append(['Column','Meaning'])
 for name in exports.HEADERS[section]:columns.append([name,'Saved permission-scoped '+name.lower()+'. Blank means not available.'])
 note=book.create_sheet('Export');note.append(['Property','Value']);note.append(['Schema version',exports.SCHEMA_VERSION]);note.append(['Section',exports.LABELS[section]]);note.append(['Purpose','Column reference only; not an import or authorization template'])
 data=BytesIO();book.save(data);book.close();data.seek(0)
 return _private(FileResponse(data,as_attachment=True,filename=section+'_columns_v1.xlsx',content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'))
