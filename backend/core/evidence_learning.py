"""Deterministic, scoped evidence reuse; human feedback never changes prior results."""
import hashlib
import json
from types import SimpleNamespace
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.http import Http404
from .evidence_models import EvidenceAnalysisRecord, EvidenceRuleRelease, EvidenceCorrection, EvidenceCorrectionDecision


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError) as error:
        raise ValidationError('Evidence must be a finite JSON value.') from error


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def current_release(project):
    return EvidenceRuleRelease.objects.filter(project_id=getattr(project, 'pk', project)).order_by('-version').first()


def analysis_context(checklist, photo, versions):
    from .field_photo_service import schema_digest
    if (photo is not None and photo.checklist_id != checklist.pk) or not checklist.project_id:
        raise ValidationError('The photo must belong to this project activity.')
    fields = ['rules_version', 'model_version', 'tool_version', 'prompt_version']
    if not isinstance(versions, dict):
        raise ValidationError('Evidence versions must be an explicit object.')
    if any(not isinstance(versions.get(key), str) or not versions[key].strip() or len(versions[key]) > 160 for key in fields):
        raise ValidationError('All evidence processing versions must be explicit.')
    return {'company_id': checklist.project.company_id, 'project_id': checklist.project_id,
            'checklist_id': checklist.pk, 'photo_id': photo.pk if photo is not None else None, 'site_id': checklist.site_id,
            'photo_sha256': photo.sha256 if photo is not None else 'none', 'schema_digest': schema_digest(checklist),
            **{key: versions[key] for key in fields}}


def analysis_key(checklist, photo, versions):
    # Additional input/release/model-file fingerprints are part of identity too.
    return digest({'scope': analysis_context(checklist, photo, versions), 'versions': versions,
                   'source_metadata': photo.metadata if photo is not None else None,
                   'source_group': photo.group if photo is not None else None})


def cached_analysis(checklist, photo, versions):
    record = EvidenceAnalysisRecord.objects.filter(cache_key=analysis_key(checklist, photo, versions)).first()
    if record is not None and digest(record.payload) != record.payload_digest:
        raise ValidationError('Saved evidence integrity could not be verified. Preserve this record and request recovery.')
    return record


find_analysis = cached_analysis


def release_references(release):
    if release is None:
        return []
    if digest(release.references) != release.digest:
        raise ValidationError('Published reference integrity could not be verified. Preserve the release and request recovery.')
    return json.loads(canonical(release.references))


def get_or_create_analysis(checklist, photo, payload, versions):
    """The first successful canonical result wins, independent of requesting actor."""
    context = analysis_context(checklist, photo, versions)
    value = json.loads(canonical(payload))
    record, created = EvidenceAnalysisRecord.objects.get_or_create(
        cache_key=analysis_key(checklist, photo, versions), defaults={**context, 'payload': value, 'payload_digest': digest(value)})
    if digest(record.payload) != record.payload_digest:
        raise ValidationError('Saved evidence integrity could not be verified. Preserve this record and request recovery.')
    return record, not created


def learning_access(actor, checklist_id):
    from .access import role_for
    from .models import Profile
    from .template_views import survey_access
    role = role_for(actor)
    if role not in {Profile.Roles.ENGINEER, Profile.Roles.QUALITY_ENGINEER, Profile.Roles.TEAM_LEAD}:
        raise PermissionDenied('Internal evidence learning requires an assigned operational role.')
    return survey_access(SimpleNamespace(user=actor), checklist_id)['checklist']


def capture_correction(actor, checklist, photo, field_id, action, reason='', mapping_id=None):
    """Capture exact source feedback only, after a real human mapping decision."""
    from .template_service import field_map
    from .field_photo_service import schema_digest
    from .access import role_for
    from .models import Profile
    if role_for(actor)==Profile.Roles.ADMIN:
        # Preserve the existing scoped mapping permission; this does not grant
        # administrators access to internal learning review or publication.
        from .template_views import survey_access
        checklist=survey_access(SimpleNamespace(user=actor),checklist.pk,edit=True)['checklist']
    else:
        checklist = learning_access(actor, checklist.pk)
    if photo.checklist_id != checklist.pk or action not in {'confirm', 'manual', 'reject'}:
        raise ValidationError('Invalid evidence correction source or action.')
    field = field_map(checklist).get(field_id)
    if not field:
        raise ValidationError('The checklist point is no longer available.')
    if len(reason) > 4000:
        raise ValidationError('Correction notes must be at most 4000 characters.')
    source = {'checklist_id': checklist.pk, 'project_id': checklist.project_id, 'company_id': checklist.project.company_id,
              'site_id': checklist.site_id, 'photo_sha256': photo.sha256,
              'schema_digest': schema_digest(checklist), 'mapping_id': mapping_id,
              'field_label': field.get('label', field_id), 'field_description': field.get('description', ''),
              'caption': str(photo.analysis_metadata.get('caption', ''))[:400]}
    return EvidenceCorrection.objects.create(checklist=checklist, photo=photo, field_id=field_id,
                                             action=action, reason=reason, source=source, captured_by=actor)


def peer_allowed(actor, checklist):
    from .access import role_for
    from .models import Profile
    learning_access(actor, checklist.pk)
    return role_for(actor) in {Profile.Roles.QUALITY_ENGINEER, Profile.Roles.TEAM_LEAD}


@transaction.atomic
def decide_correction(actor, checklist_id, case_id, decision, reason):
    from .governance_views import lock_governance
    lock_governance(actor)
    checklist = learning_access(actor, checklist_id)
    case = get_object_or_404(EvidenceCorrection, pk=case_id, checklist=checklist)
    if not peer_allowed(actor, checklist) or case.captured_by_id == actor.pk:
        raise PermissionDenied('A different assigned Quality Engineer or Team Lead must review this correction.')
    if decision not in {'approved', 'rejected'} or not isinstance(reason, str) or not reason.strip() or len(reason) > 4000:
        raise ValidationError('Choose approve or reject and provide a review reason.')
    if EvidenceCorrectionDecision.objects.filter(correction=case).exists():
        raise ValidationError('This correction already has an immutable peer decision.')
    return EvidenceCorrectionDecision.objects.create(correction=case, actor=actor, decision=decision, reason=reason.strip())


@transaction.atomic
def publish_release(actor, checklist_id, case_ids, reason):
    from .governance_views import lock_governance
    lock_governance(actor)
    checklist = learning_access(actor, checklist_id)
    if not peer_allowed(actor, checklist):
        raise PermissionDenied('Only an assigned Quality Engineer or Team Lead may publish reviewed references.')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 4000:
        raise ValidationError('A release reason is required.')
    if not isinstance(case_ids, list) or not case_ids or len(case_ids) > 100 or any(type(pk) is not int or pk < 1 for pk in case_ids) or len(set(case_ids)) != len(case_ids):
        raise ValidationError('Select one to 100 distinct approved corrections.')
    cases = list(EvidenceCorrection.objects.filter(pk__in=case_ids).select_related('checklist__project', 'peer_decision'))
    if len(cases) != len(case_ids):
        raise ValidationError('A selected correction is unavailable.')
    for case in cases:
        learning_access(actor, case.checklist_id)
        if case.checklist.project_id != checklist.project_id or not hasattr(case, 'peer_decision') or case.peer_decision.decision != 'approved':
            raise ValidationError('Every reference must be peer approved in this project.')
    previous = current_release(checklist.project_id)
    references = list(previous.references) if previous else []
    used = {r['correction_id'] for r in references}
    if all(case.pk in used for case in cases):
        raise ValidationError('These corrections are already included in the current release.')
    for case in sorted(cases, key=lambda value: value.pk):
        if case.pk in used:
            continue
        references.append({'correction_id': case.pk, 'field_id': case.field_id,
                           'polarity': 'negative' if case.action == 'reject' else 'positive',
                           **case.source})
    release = EvidenceRuleRelease.objects.create(project=checklist.project, version=(previous.version + 1) if previous else 1,
                                                 references=references, digest=digest(references), published_by=actor, reason=reason.strip())
    return release


def learning_state(actor, checklist_id):
    checklist = learning_access(actor, checklist_id)
    reviewer = peer_allowed(actor, checklist)
    cases = []
    for case in checklist.evidence_corrections.select_related('peer_decision', 'captured_by').order_by('-pk'):
        decision = getattr(case, 'peer_decision', None)
        cases.append({'id': case.pk, 'photo_id': case.photo_id, 'field_id': case.field_id, 'action': case.action,
                      'reason': case.reason, 'created_by': case.captured_by.get_full_name() or case.captured_by.username,
                      'decision': decision.decision if decision else 'pending',
                      'decision_reason': decision.reason if decision else '', 'source': case.source,
                      'can_decide': reviewer and not decision and case.captured_by_id != actor.pk})
    releases = []
    allowed = {checklist.pk: True}
    for release in EvidenceRuleRelease.objects.filter(project=checklist.project).order_by('-version'):
        references = []
        for reference in release.references:
            site = reference.get('checklist_id')
            if site not in allowed:
                try:
                    learning_access(actor, site)
                    allowed[site] = True
                except (PermissionDenied, Http404):
                    allowed[site] = False
            if allowed[site]:
                references.append(reference)
        releases.append({'id': release.pk, 'version': release.version, 'digest': release.digest,
                         'reason': release.reason, 'created_at': release.created_at.isoformat(),
                         'references': references})
    return {'current_release': releases[0] if releases else None, 'cases': cases, 'releases': releases, 'can_publish': reviewer}
