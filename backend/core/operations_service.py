"""Bounded operational summaries; never invoke inference or expose job payloads."""
import logging
import os
from pathlib import Path
import re

from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Count,Max,Q
from django.utils import timezone


logger=logging.getLogger(__name__)


def release_id():
    value=getattr(settings,'ISURVIX_RELEASE_ID','')
    return value if isinstance(value,str) and re.fullmatch('[0-9a-f]{40}',value) else 'unknown'


def database_ready():
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
        if cursor.fetchone()!=(1,):return False
    executor=MigrationExecutor(connection)
    return not executor.migration_plan(executor.loader.graph.leaf_nodes())


def readiness(request_id=None):
    try:
        if not database_ready():return False
        for key,mode in [('MEDIA_ROOT',os.R_OK|os.W_OK),('STATIC_ROOT',os.R_OK)]:
            value=getattr(settings,key,None)
            if not value or not Path(value).is_dir() or not os.access(value,mode):return False
        upload_tmp=getattr(settings,'FILE_UPLOAD_TEMP_DIR',None)
        if upload_tmp and (not Path(upload_tmp).is_dir() or not os.access(upload_tmp,os.W_OK)):return False
        return True
    except Exception:
        # Exception messages can include private DB paths/credentials. Log only a
        # stable code; use privileged server diagnostics for investigation.
        logger.warning('operations.readiness_unavailable',extra={'event':'operations.readiness_unavailable','release_id':release_id(),'request_id':request_id})
        return False


def summary(request_id=None):
    from .photo_models import PhotoJob
    from .survey_processing import ACTIVE,STAGES
    from .survey_processing_models import SurveyProcessingJob,SurveyUploadSession
    from .remote_worker_models import RemoteSurveyLease,RemoteWorkerProject
    now=timezone.now()
    def counts(model,fallback):
        statuses={value for value,_label in (model._meta.get_field('status').choices or ())} or set(fallback)
        result={}
        for row in model.objects.values('status').annotate(count=Count('pk')):
            key=row['status'] if row['status'] in statuses else 'other'
            result[key]=result.get(key,0)+row['count']
        return result
    # ACTIVE deliberately includes queued for worker claiming. A queued PC-offline
    # job is not an abandoned running job and must not inflate stale-lease counts.
    running=ACTIVE-{'queued'}
    stale=SurveyProcessingJob.objects.filter(status__in=running).filter(Q(lease_until__lt=now)|Q(lease_until__isnull=True)).count()
    leases=RemoteSurveyLease.objects.filter(job__status__in=running,job__lease_owner__startswith='remote:')
    last=RemoteSurveyLease.objects.aggregate(value=Max('heartbeat_at'))['value']
    return {'release':release_id(),'ready':readiness(request_id),'survey_jobs':counts(SurveyProcessingJob,STAGES),
            'photo_jobs':counts(PhotoJob,{'queued','running','completed','failed'}),
            'stale_survey_jobs':stale,'open_upload_sessions':SurveyUploadSession.objects.filter(finished_at__isnull=True).count(),
            'remote_worker':{'enabled_projects':RemoteWorkerProject.objects.filter(enabled=True).count(),
                'active_leases':leases.filter(job__lease_until__gt=now).count(),
                'expired_leases':leases.filter(Q(job__lease_until__lt=now)|Q(job__lease_until__isnull=True)).count(),
                'last_heartbeat_at':last.isoformat() if last else None}}
