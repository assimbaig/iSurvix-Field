from django.urls import include, path

from . import views, template_views, selection_views, field_intake_views
from . import account_views
from . import standard_checklist_views
from . import checklist_wizard_views
from .legacy_routes import protected_legacy
from .private_files import checklist_file

urlpatterns = [
    path('governance/onboarding/', include('core.onboarding_urls')),
    path('private/checklists/<int:checklist_id>/file/', checklist_file, name='private_checklist_file'),
    path('governance/industries/',include('core.industry_urls')),
    path('work/review-routes/',include('core.review_route_urls')),
    path('devadmin/checklist-wizard/',checklist_wizard_views.wizard,name='checklist_wizard'),
    path('devadmin/checklist-library/',checklist_wizard_views.library,name='checklist_library'),
    path('devadmin/checklist-wizard/workbook/',checklist_wizard_views.workbook,name='checklist_wizard_workbook'),
    path('devadmin/checklist-wizard/<int:template_id>/',checklist_wizard_views.edit,name='checklist_wizard_edit'),
    path('devadmin/checklist-wizard/<int:template_id>/export/',checklist_wizard_views.export,name='checklist_wizard_export'),
    path('governance/', include('core.governance_urls')),
    path('evidence/', include('core.evidence_urls')),
    path('custom-checklist/<int:checklist_id>/site-information/', field_intake_views.site_information, name='checklist_site_information'),
    path('custom-checklist/<int:checklist_id>/review/', template_views.custom_review, name='custom_checklist_review'),
    path('devadmin/checklist-templates/', template_views.template_builder, name='checklist_templates'),
    path('devadmin/checklist-templates/select/', selection_views.select_checklist, name='checklist_template_select'),
    path('devadmin/checklist-templates/standards/', standard_checklist_views.library, name='standard_checklists'),
    path('devadmin/checklist-templates/standards/preview/', standard_checklist_views.preview, name='standard_checklist_preview'),
    path('devadmin/checklist-templates/<int:template_id>/', template_views.template_builder, name='checklist_template_edit'),
    path('devadmin/checklist-templates/<int:template_id>/recommendations/', template_views.template_recommendations, name='checklist_template_recommendations'),
    path('devadmin/checklist-templates/<int:template_id>/logo/<str:slot>/', template_views.template_logo, name='checklist_template_logo'),
    path('custom-checklist/<int:checklist_id>/', template_views.custom_survey, name='custom_checklist'),
    path('custom-checklist/<int:checklist_id>/save/', template_views.custom_save, name='custom_checklist_save'),
    path('custom-checklist/<int:checklist_id>/submit/', template_views.custom_submit, name='custom_checklist_submit'),
    path('custom-checklist/<int:checklist_id>/download/', template_views.custom_download, name='custom_checklist_download'),
    path('custom-checklist/<int:checklist_id>/upload/<str:field_id>/', template_views.custom_upload, name='custom_checklist_upload'),
    path('custom-checklist/<int:checklist_id>/photo/<str:field_id>/<int:index>/', template_views.custom_photo, name='custom_checklist_photo'),
    path('custom-checklist/<int:checklist_id>/photo/<str:field_id>/<int:index>/delete/', template_views.custom_photo_delete, name='custom_checklist_photo_delete'),
    path('custom-checklist/<int:checklist_id>/logo/<int:slot>/', template_views.custom_client_logo, name='custom_client_logo'),
    path("", account_views.home, name="home"),
    path("login/", account_views.sign_in, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("devadmin/", account_views.retired_admin, name="dev_admin"),
    path("devadmin/users/<int:user_id>/edit/", account_views.retired_admin, name="admin_user_edit"),
    path("devadmin/users/<int:user_id>/delete/", account_views.retired_admin, name="admin_user_delete"),
    path("devadmin/locked/<int:profile_id>/unlock/", account_views.retired_admin, name="admin_user_unlock"),
    path("<str:path>/", account_views.home, name="user_dashboard"),
    path("<str:path>/checklists/new/", account_views.retired_action, name="engineer_checklist_new"),
    path("<str:path>/checklists/<int:checklist_id>/", views.engineer_checklist_edit, name="engineer_checklist_edit"),
    path(
        "<str:path>/checklists/<int:checklist_id>/autosave/",
        views.engineer_checklist_autosave,
        name="engineer_checklist_autosave",
    ),
    path(
        "<str:path>/checklists/<int:checklist_id>/submit/",
        views.engineer_checklist_submit,
        name="engineer_checklist_submit",
    ),
    path(
        "<str:path>/checklists/<int:checklist_id>/delete/",
        views.engineer_checklist_delete,
        name="engineer_checklist_delete",
    ),
    path(
        "<str:path>/checklists/<int:checklist_id>/download/",
        views.engineer_checklist_download,
        name="engineer_checklist_download",
    ),
    path(
        "checklists/<int:checklist_id>/review/",
        views.checklist_review_update,
        name="checklist_review_update",
    ),
    path("locations/add/", views.location_add, name="location_add"),
    path("locations/import/", views.location_import, name="location_import"),
    path("locations/delete-all/", views.location_delete_all, name="location_delete_all"),
    path("locations/<int:location_id>/delete/", views.location_delete, name="location_delete"),
    path("work/assign/", account_views.governed_assignment, name="assign_work"),
    path("work/<int:work_id>/edit/", views.work_edit, name="work_edit"),
    path("work/<int:work_id>/delete/", views.work_delete, name="work_delete"),
    path("work/<int:work_id>/update/", views.update_work_status, name="update_work_status"),
    path("work/<int:work_id>/complete/", views.complete_work, name="complete_work"),
    path("work/<int:work_id>/create-checklist/", views.create_checklist_from_work, name="create_checklist_from_work"),
    
    # New detailed checklist URLs
    path("checklist/<int:checklist_id>/detail/", views.checklist_detail_view, name="checklist_detail"),
    path("checklist/<int:checklist_id>/data/", views.checklist_data_api, name="checklist_data_api"),
    path("checklist/<int:checklist_id>/autosave/", views.checklist_autosave_api, name="checklist_autosave_api"),
    path("checklist/<int:checklist_id>/submit/", views.checklist_submit, name="checklist_submit"),
    path("checklist/<int:checklist_id>/upload-image/", views.checklist_upload_image, name="checklist_upload_image"),
    path("checklist/<int:checklist_id>/upload-zip/", views.checklist_upload_zip, name="checklist_upload_zip"),
    path("checklist/image/delete/", views.checklist_delete_image, name="checklist_delete_image"),
    path("checklist/<int:checklist_id>/download-zip/", views.checklist_download_zip, name="checklist_download_zip"),
    path("checklist/equipment/<int:equipment_id>/delete/", views.checklist_delete_equipment, name="checklist_delete_equipment"),
    path("checklist/electrical/<int:electrical_id>/delete/", views.checklist_delete_electrical, name="checklist_delete_electrical"),
]

# Retire destructive/unscoped legacy tools; originals stay in the database/media.
retired = {'admin_user_edit', 'admin_user_delete', 'admin_user_unlock',
           'location_add', 'location_import', 'location_delete', 'location_delete_all',
           'work_edit', 'work_delete', 'update_work_status', 'complete_work',
           'checklist_upload_zip', 'checklist_delete_equipment', 'checklist_delete_electrical',
           'engineer_checklist_delete', 'checklist_delete_image'}
legacy = {'engineer_checklist_edit', 'engineer_checklist_autosave', 'engineer_checklist_submit',
          'engineer_checklist_download', 'checklist_review_update', 'checklist_detail',
          'checklist_data_api', 'checklist_autosave_api', 'checklist_submit',
          'checklist_upload_image', 'checklist_download_zip', 'create_checklist_from_work'}
for pattern in urlpatterns:
    name = getattr(pattern, 'name', None)
    if name in retired:
        pattern.callback = account_views.retired_action
    elif name in legacy:
        pattern.callback = protected_legacy(pattern.callback, name)
