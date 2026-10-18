from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import (
	Checklist, Profile, Project, GeoLocation, WorkAssignment,
	ChecklistSection, ChecklistImage, DCPowerSystemData, TowerEquipment, ElectricalData, ChecklistTemplate
)


class OperationalAdminBoundary:
	"""Super Admin's account powers never grant engineering-record access."""
	def _operational_allowed(self, request):
		from .access import is_super_admin
		return not is_super_admin(request.user)

	def has_module_permission(self, request):
		return self._operational_allowed(request) and super().has_module_permission(request)

	def has_view_permission(self, request, obj=None):
		return self._operational_allowed(request) and super().has_view_permission(request, obj)

	def has_add_permission(self, request):
		return self._operational_allowed(request) and super().has_add_permission(request)

	def has_change_permission(self, request, obj=None):
		return self._operational_allowed(request) and super().has_change_permission(request, obj)

	def has_delete_permission(self, request, obj=None):
		return self._operational_allowed(request) and super().has_delete_permission(request, obj)


def client_boundary_form(base, request):
	"""Keep retired admin forms subject to Client ownership rules too."""
	class ClientBoundaryForm(base):
		def clean(self):
			data = super().clean()
			from .access import is_super_admin
			if is_super_admin(request.user) and data.get('role') == Profile.Roles.CLIENT:
				previous = Profile.objects.filter(pk=self.instance.pk).first() if self.instance.pk else None
				if not previous or previous.role != Profile.Roles.CLIENT or any(getattr(data.get(field), 'pk', None) != getattr(previous, field + '_id') for field in ('project', 'company') if field in data):
					raise ValidationError('Only a project Admin may create or assign Client accounts.')
			return data
	return ClientBoundaryForm


class ProfileInline(admin.StackedInline):
	model = Profile
	can_delete = False
	extra = 0
	def get_formset(self, request, obj=None, **kwargs):
		formset = super().get_formset(request, obj, **kwargs)
		formset.form = client_boundary_form(formset.form, request)
		return formset
	def get_readonly_fields(self, request, obj=None):
		from .access import is_super_admin
		return () if is_super_admin(request.user) else ('admin_industry',)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
	list_display = ('user', 'role', 'project', 'path', 'is_locked', 'failed_attempts')
	search_fields = ('user__username', 'path', 'project__name')
	list_filter = ('role', 'project', 'is_locked')
	actions = ['unlock_profiles']
	def get_form(self, request, obj=None, **kwargs):
		return client_boundary_form(super().get_form(request, obj, **kwargs), request)

	def get_readonly_fields(self, request, obj=None):
		from .access import is_super_admin
		return () if is_super_admin(request.user) else ('admin_industry',)

	def unlock_profiles(self, request, queryset):
		queryset.update(is_locked=False, failed_attempts=0)
	unlock_profiles.short_description = "Unlock selected profiles"


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
	readonly_fields = ('client_organization',)
	list_display = ('name', 'template_file')
	search_fields = ('name',)


@admin.register(Checklist)
class ChecklistAdmin(OperationalAdminBoundary, admin.ModelAdmin):
	list_display = ('id', 'user', 'project', 'site_id', 'status', 'created_at')
	list_filter = ('status', 'project')
	search_fields = ('site_id', 'user__username', 'project__name')
	readonly_fields = ('checklist_template', 'schema_snapshot', 'branding_snapshot')


@admin.register(ChecklistTemplate)
class ChecklistTemplateAdmin(OperationalAdminBoundary, admin.ModelAdmin):
	list_display = ('name', 'version', 'published', 'created_at')
	readonly_fields = ('family_id', 'version', 'created_by', 'created_at')

	def has_add_permission(self, request):
		return False  # Use the validated checklist designer.

	def has_delete_permission(self, request, obj=None):
		return False

	def get_readonly_fields(self, request, obj=None):
		return [field.name for field in self.model._meta.fields] if obj and obj.published else super().get_readonly_fields(request, obj)


@admin.register(GeoLocation)
class GeoLocationAdmin(OperationalAdminBoundary, admin.ModelAdmin):
	list_display = ('name', 'latitude', 'longitude', 'project', 'created_by', 'created_at')
	list_filter = ('project', 'created_at')
	search_fields = ('name', 'notes', 'created_by__username')
	readonly_fields = ('created_at',)


@admin.register(WorkAssignment)
class WorkAssignmentAdmin(OperationalAdminBoundary, admin.ModelAdmin):
	list_display = ('site_id', 'assigned_to', 'assigned_by', 'project', 'status', 'created_at', 'submitted_at')
	list_filter = ('status', 'project', 'created_at')
	search_fields = ('site_id', 'description', 'assigned_to__username', 'assigned_by__username')
	readonly_fields = ('created_at', 'started_at', 'submitted_at', 'completed_at')
	fieldsets = (
		('Work Details', {
			'fields': ('site_id', 'latitude', 'longitude', 'description')
		}),
		('Assignment', {
			'fields': ('assigned_to', 'assigned_by', 'project')
		}),
		('Status', {
			'fields': ('status', 'engineer_notes')
		}),
		('Timeline', {
			'fields': ('created_at', 'started_at', 'submitted_at', 'completed_at')
		}),
	)


class UserAdmin(DjangoUserAdmin):
	inlines = [ProfileInline]

	def get_inline_instances(self, request, obj=None):
		if obj is None:
			return []
		return super().get_inline_instances(request, obj)


# Register new checklist models
@admin.register(ChecklistSection)
class ChecklistSectionAdmin(OperationalAdminBoundary, admin.ModelAdmin):
	list_display = ('checklist', 'section_name', 'row_number', 'question')
	list_filter = ('section_name', 'checklist__project')
	search_fields = ('question', 'answer', 'remarks')
	ordering = ['checklist', 'row_number']


@admin.register(ChecklistImage)
class ChecklistImageAdmin(OperationalAdminBoundary, admin.ModelAdmin):
	list_display = ('checklist', 'section', 'column_position', 'uploaded_at')
	list_filter = ('uploaded_at', 'column_position')
	readonly_fields = ('uploaded_at',)


@admin.register(DCPowerSystemData)
class DCPowerSystemDataAdmin(OperationalAdminBoundary, admin.ModelAdmin):
	list_display = ('checklist', 'row_number', 'field_label', 'field_value')
	list_filter = ('checklist__project',)
	search_fields = ('field_label', 'field_value')
	ordering = ['checklist', 'row_number']


@admin.register(TowerEquipment)
class TowerEquipmentAdmin(OperationalAdminBoundary, admin.ModelAdmin):
	list_display = ('checklist', 'operator_type', 'equipment_type', 'row_number', 'model_name', 'position_index')
	list_filter = ('operator_type', 'equipment_type', 'checklist__project')
	search_fields = ('model_name',)
	ordering = ['checklist', 'operator_type', 'equipment_type', 'position_index']


@admin.register(ElectricalData)
class ElectricalDataAdmin(OperationalAdminBoundary, admin.ModelAdmin):
	list_display = ('checklist', 'row_number', 'voltage', 'current_r', 'current_y', 'current_b')
	list_filter = ('checklist__project',)
	ordering = ['checklist', 'position_index']


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
