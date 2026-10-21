from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from copy import deepcopy
import uuid


class ChecklistTemplate(models.Model):
	"""An editable draft or an immutable, published checklist revision."""
	checklist_required = models.BooleanField(default=False, help_text='Opt in survey types to AI checklist and drawing preparation. Inspection modules are excluded.')
	company_logo = models.ImageField(upload_to='client_logos/', blank=True)
	family_id = models.UUIDField(default=uuid.uuid4, editable=False)
	version = models.PositiveIntegerField(default=1)
	name = models.CharField(max_length=160)
	definition = models.JSONField(default=dict)
	published = models.BooleanField(default=False)
	client_left_name = models.CharField(max_length=80, default='Nokia', blank=True)
	client_right_name = models.CharField(max_length=80, default='TAWAL', blank=True)
	client_left_logo = models.ImageField(upload_to='client_logos/', blank=True)
	client_right_logo = models.ImageField(upload_to='client_logos/', blank=True)
	created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['name', '-version']
		constraints = [models.UniqueConstraint(fields=['family_id', 'version'], name='unique_checklist_template_revision')]

	def __str__(self):
		return f'{self.name} · v{self.version}'

	def save(self, *args, **kwargs):
		from .template_service import validate_definition
		validate_definition(self.definition)
		if self.pk:
			previous = type(self).objects.get(pk=self.pk)
			if previous.published:
				fields = ['family_id', 'version', 'name', 'definition', 'published', 'checklist_required', 'company_logo', 'client_left_name', 'client_right_name', 'client_left_logo', 'client_right_logo']
				if any(getattr(previous, field) != getattr(self, field) for field in fields):
					raise ValidationError('Published templates are locked. Duplicate this revision to make changes.')
		return super().save(*args, **kwargs)

	def branding(self):
		result = {'clients': [
			{'name': self.client_left_name, 'logo': self.client_left_logo.name or ''},
			{'name': self.client_right_name, 'logo': self.client_right_logo.name or ''},
		]}
		if self.company_logo:
			result['company_logo'] = self.company_logo.name
		return result


def project_template_upload_path(instance: "Project", filename: str) -> str:
	slug = instance.name.strip().lower().replace(" ", "-") or "project"
	return f"project_templates/{slug}/{filename}"


class Company(models.Model):
	name = models.CharField(max_length=160, unique=True)
	description = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	class Meta:
		ordering = ['name']
	def __str__(self):
		return self.name


class IndustryCatalog(models.Model):
	code = models.SlugField(max_length=20, unique=True)
	name = models.CharField(max_length=100, unique=True)
	description = models.TextField(blank=True)
	workflow_family = models.CharField(max_length=20, choices=[('telecom','Telecom'),('construction','Construction'),('other','Other')], default='other')
	is_active = models.BooleanField(default=True)
	class Meta:
		ordering = ['name']
	def __str__(self):
		return self.name
	@property
	def edit_token(self):
		from .industry_service import industry_token
		return industry_token(self)
	def save(self,*args,**kwargs):
		if self.pk:
			previous=type(self).objects.get(pk=self.pk)
			if previous.workflow_family!=self.workflow_family:
				raise ValidationError('An existing industry workflow family cannot be changed.')
			if previous.code!=self.code and not getattr(self,'_allow_code_rename',False):
				raise ValidationError('Rename an industry through its governed editor so project references remain consistent.')
		return super().save(*args,**kwargs)
	def delete(self,*args,**kwargs):
		raise ValidationError('Deactivate industries to preserve historical project meaning.')


class ClientOrganization(models.Model):
	legacy_company = models.OneToOneField(Company, null=True, blank=True, on_delete=models.PROTECT, related_name='imported_client_organization')
	name = models.CharField(max_length=160)
	description = models.TextField(blank=True)
	company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='client_organizations')
	industry = models.ForeignKey(IndustryCatalog, on_delete=models.PROTECT, related_name='client_organizations')
	created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_client_organizations')
	created_at = models.DateTimeField(auto_now_add=True)
	class Meta:
		ordering = ['name','pk']
		constraints = [models.UniqueConstraint(fields=['company','industry','name'], name='unique_tenant_industry_client')]
	def __str__(self):
		return self.name


class Project(models.Model):
	class Industry(models.TextChoices):
		TELECOM = 'telecom', 'Telecom'
		CONSTRUCTION = 'construction', 'Construction'
	client_organization = models.ForeignKey(ClientOrganization, null=True, blank=True, on_delete=models.PROTECT, related_name='projects')
	industry = models.CharField(max_length=20, default=Industry.TELECOM)
	company = models.ForeignKey(Company, null=True, blank=True, on_delete=models.PROTECT, related_name='projects')
	administrator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='administered_projects')
	name = models.CharField(max_length=120, unique=True)
	description = models.TextField(blank=True)
	template_file = models.FileField(upload_to=project_template_upload_path, blank=True, null=True)
	checklist_template = models.ForeignKey(ChecklistTemplate, null=True, blank=True, on_delete=models.PROTECT, related_name='projects')
	review_layers = models.PositiveSmallIntegerField(null=True, blank=True, default=None, choices=[(3,'3 layers: Engineer - QA - Team Lead'),(4,'4 layers: Engineer - QA - Team Lead - Client')])
	class Meta:
		constraints = [models.CheckConstraint(condition=models.Q(review_layers__isnull=True)|models.Q(review_layers__in=[3,4]),name='valid_project_review_layers')]

	def save(self, *args, **kwargs):
		if self.review_layers not in (None,3,4) or isinstance(self.review_layers,bool):
			raise ValidationError('Choose a three-layer or four-layer project workflow.')
		if self.client_organization_id and (self.client_organization.company_id!=self.company_id or self.client_organization.industry.code!=self.industry):
			raise ValidationError('Client organization must match the project company and industry.')
		if self.checklist_template_id and not self.checklist_template.published:
			raise ValidationError('Projects may use published checklist revisions only.')
		if self.checklist_template_id:
			from .standard_checklist_service import validate_standard_project
			validate_standard_project(self.checklist_template,self)
		return super().save(*args, **kwargs)

	def __str__(self) -> str:
		return self.name

	def get_industry_display(self):
		return IndustryCatalog.objects.filter(code=self.industry).values_list('name',flat=True).first() or self.industry


class Profile(models.Model):
	class Roles(models.TextChoices):
		ADMIN = 'ADMIN', 'Project Admin'
		SUPER_ADMIN = 'SUPER_ADMIN', 'Super Admin'
		TEAM_LEAD = 'TEAM_LEAD', 'Team Lead'
		ENGINEER = 'ENGINEER', 'Engineer'
		QUALITY_ENGINEER = 'QUALITY_ENGINEER', 'Quality Engineer'
		CLIENT = 'CLIENT', 'Client'
		PROJECT_MANAGER = 'project_manager', 'Project Manager'

	admin_industry_pending = models.BooleanField(default=False)
	admin_industry = models.ForeignKey(IndustryCatalog, null=True, blank=True, on_delete=models.PROTECT, related_name='industry_admins')
	company = models.ForeignKey(Company, null=True, blank=True, on_delete=models.PROTECT, related_name='profiles')
	user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
	role = models.CharField(max_length=20, choices=Roles.choices)
	project = models.ForeignKey(
		Project,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="profiles",
	)
	path = models.CharField(
		max_length=10,
		unique=True,
		null=True,
		blank=True,
		help_text="Use values like TL1, TL2, Eng1, Eng2",
	)
	failed_attempts = models.PositiveSmallIntegerField(default=0)
	is_locked = models.BooleanField(default=False)

	def save(self,*args,**kwargs):
		result=super().save(*args,**kwargs)
		# Compatibility for trusted legacy primary-project assignment: claim only an
		# unowned project. A later account/grant can never replace an existing owner.
		if self.role==self.Roles.ADMIN and self.project_id and not self.user.is_superuser:
			unowned=Project.objects.filter(pk=self.project_id,administrator__isnull=True)
			if self.company_id is not None:unowned=unowned.filter(company_id=self.company_id)
			if self.admin_industry_id:unowned=unowned.filter(industry=self.admin_industry.code)
			if not self.admin_industry_pending:unowned.update(administrator_id=self.user_id)
		return result

	def __str__(self) -> str:
		return f"{self.user.username} ({self.get_role_display()})"


class ProjectMembership(models.Model):
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='project_memberships')
	project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='memberships')
	is_active = models.BooleanField(default=True)
	is_primary = models.BooleanField(default=False)
	expires_at = models.DateTimeField(null=True, blank=True)
	granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='granted_project_memberships')
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	@property
	def is_effective(self):
		from django.utils import timezone
		return self.is_active and (self.expires_at is None or self.expires_at>timezone.now())
	class Meta:
		constraints = [models.UniqueConstraint(fields=['user','project'], name='unique_user_project_membership')]



class Checklist(models.Model):
	class WorkflowType(models.TextChoices):
		TELECOM_SURVEY = 'telecom_survey', 'Telecom survey'
		TELECOM_INSPECTION = 'telecom_inspection', 'Telecom inspection'
		CONSTRUCTION_INSPECTION = 'construction_inspection', 'Construction inspection'
	class GovernanceMode(models.TextChoices):
		LEGACY = 'legacy', 'Engineer - Team Lead - Client'
		INDEPENDENT = 'independent', 'Independent L1 - L2 - L3 review'
	workflow_type = models.CharField(max_length=32, choices=WorkflowType.choices, default=WorkflowType.TELECOM_SURVEY)
	governance_mode = models.CharField(max_length=20, choices=GovernanceMode.choices, default=GovernanceMode.LEGACY)
	asset_reference = models.CharField(max_length=200, blank=True)
	coordinate_reference = models.JSONField(default=dict, blank=True)
	class Status(models.TextChoices):
		DRAFT = "DRAFT", "Draft"
		SUBMITTED = "SUBMITTED", "Submitted"
		REVIEW = "REVIEW", "Review"
		FINAL = "FINAL", "Final"
		PARTIAL = "PARTIAL", "Partially approved"
		REJECTED = "REJECTED", "Rejected"

	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
	project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="checklists")
	site_id = models.CharField(max_length=120, blank=True)
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
	comment = models.TextField(blank=True)
	comment_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="checklist_comments"
	)
	answer_data = models.JSONField(default=dict, blank=True)
	intake_metadata = models.JSONField(default=dict, blank=True)
	remark_data = models.JSONField(default=dict, blank=True)
	image_data = models.JSONField(default=dict, blank=True)
	template_copy = models.FileField(upload_to="checklists/", blank=True, null=True)
	checklist_template = models.ForeignKey(ChecklistTemplate, null=True, blank=True, on_delete=models.PROTECT, related_name='checklists')
	schema_snapshot = models.JSONField(default=dict, blank=True)
	branding_snapshot = models.JSONField(default=dict, blank=True)
	section_approvals = models.JSONField(default=dict, blank=True)
	review_history = models.JSONField(default=list, blank=True)
	quality_reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='quality_checklists')
	quality_approval = models.JSONField(default=dict, blank=True)
	client_approval = models.JSONField(default=dict, blank=True)
	client_review_required = models.BooleanField(null=True, default=None, blank=True)
	client_review_routed_at = models.DateTimeField(null=True, blank=True)
	client_review_completed_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def save(self, *args, **kwargs):
		if self.pk and self.status == self.Status.SUBMITTED:
			previous_status = type(self).objects.filter(pk=self.pk).values_list('status', flat=True).first()
			if previous_status != self.Status.SUBMITTED:
				from .survey_processing import require_engineer_review
				require_engineer_review(self)
		if self._state.adding and self.project_id:
			if self.project.review_layers in (3,4):
				if not isinstance(self.intake_metadata,dict):
					raise ValidationError('Task intake context must be an object.')
				self.intake_metadata={**self.intake_metadata,'project_review_layers':self.project.review_layers}
				self.governance_mode=self.GovernanceMode.INDEPENDENT
				self.client_review_required=self.project.review_layers==4
			template = self.checklist_template or self.project.checklist_template
			if template:
				if not template.published:
					raise ValidationError('Only a published checklist template can be assigned to a survey.')
				from .standard_checklist_service import validate_standard_project
				validate_standard_project(template,self.project,self.workflow_type)
				self.checklist_template = template
				self.schema_snapshot = deepcopy(template.definition)
				self.branding_snapshot = deepcopy(template.branding())
		elif self.pk:
			previous=type(self).objects.filter(pk=self.pk).values_list('intake_metadata',flat=True).first()
			old_layers=previous.get('project_review_layers') if isinstance(previous,dict) else None
			new_layers=self.intake_metadata.get('project_review_layers') if isinstance(self.intake_metadata,dict) else None
			if old_layers!=new_layers or (old_layers in (3,4) and self.governance_mode!=self.GovernanceMode.INDEPENDENT):
				raise ValidationError('The task project approval policy is frozen. Existing activities cannot be silently converted.')
		return super().save(*args, **kwargs)

	def __str__(self) -> str:
		return f"{self.user.username} - {self.project.name} - {self.site_id or self.id}"

	@property
	def workflow_stage(self):
		from .workflow_service import workflow_stage
		return workflow_stage(self)

	@property
	def workflow_label(self):
		from .workflow_service import workflow_label
		return workflow_label(self)

	@property
	def can_client_decide(self):
		from .workflow_service import can_client_decide
		return can_client_decide(self)

	@property
	def client_review_token(self):
		from .access import client_review_token
		return client_review_token(self)

	@property
	def has_zip(self) -> bool:
		zip_info = (self.answer_data or {}).get("zip_upload")
		if isinstance(zip_info, dict):
			return bool(zip_info.get("path"))
		return False


class GeoLocation(models.Model):
	name = models.CharField(max_length=200, help_text="Location name or description")
	latitude = models.DecimalField(max_digits=10, decimal_places=7, help_text="Latitude coordinate")
	longitude = models.DecimalField(max_digits=10, decimal_places=7, help_text="Longitude coordinate")
	project = models.ForeignKey(
		Project,
		on_delete=models.CASCADE,
		related_name="locations",
		null=True,
		blank=True
	)
	created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
	created_at = models.DateTimeField(auto_now_add=True)
	notes = models.TextField(blank=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self) -> str:
		return f"{self.name} ({self.latitude}, {self.longitude})"


class WorkAssignment(models.Model):
	class Status(models.TextChoices):
		PENDING = "PENDING", "Pending"
		IN_PROGRESS = "IN_PROGRESS", "In Progress"
		SUBMITTED = "SUBMITTED", "Submitted"
		COMPLETED = "COMPLETED", "Completed"
		CLIENT_REVIEW = "CLIENT_REVIEW", "Awaiting client approval"
	
	site_id = models.CharField(max_length=120, unique=True, help_text="Site identification number (unique)")
	latitude = models.DecimalField(max_digits=10, decimal_places=7, help_text="Site latitude")
	longitude = models.DecimalField(max_digits=10, decimal_places=7, help_text="Site longitude")
	description = models.TextField(help_text="Work description and requirements")
	
	assigned_to = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="assigned_works"
	)
	assigned_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="work_assignments_created"
	)
	project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="work_assignments")
	
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
	checklist = models.OneToOneField(
		'Checklist',
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="work_assignment",
		help_text="Auto-created checklist for this work"
	)
	created_at = models.DateTimeField(auto_now_add=True)
	started_at = models.DateTimeField(null=True, blank=True)
	submitted_at = models.DateTimeField(null=True, blank=True)
	completed_at = models.DateTimeField(null=True, blank=True)
	
	engineer_notes = models.TextField(blank=True, help_text="Notes from engineer")

	class Meta:
		ordering = ['-created_at']

	def __str__(self) -> str:
		return f"{self.site_id} - {self.assigned_to.username} ({self.get_status_display()})"


@receiver(post_save, sender=User)
def create_profile_for_user(sender, instance, created, **kwargs):
	if created:
		Profile.objects.get_or_create(user=instance, defaults={"role": Profile.Roles.ENGINEER})


# ===== NEW DETAILED CHECKLIST MODELS =====

def checklist_image_upload_path(instance, filename):
	"""Upload path for checklist images"""
	return f"checklist_images/{instance.checklist.id}/{instance.section}/{filename}"


class ChecklistSection(models.Model):
	"""
	Stores answers for each section question
	
	Column Mapping by Section:
	- General (rows 4-18): Question in AB (merged), Answer in CDEF (merged)
	- CIVIL & onwards (rows 22-185): Question in B, Remarks in DE (merged), Images in F,G,H...
	"""
	checklist = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name="sections")
	section_name = models.CharField(max_length=100)  # e.g., "General", "CIVIL & SITE GENERAL"
	row_number = models.IntegerField()  # Excel row number
	question = models.TextField(blank=True)  # From column AB (General) or B (other sections)
	answer = models.TextField(blank=True)  # To column CDEF (merged) for General section
	remarks = models.TextField(blank=True)  # To column DE (merged) for other sections
	
	class Meta:
		ordering = ['row_number']
		unique_together = ['checklist', 'section_name', 'row_number']
	
	def __str__(self):
		return f"{self.checklist.id} - {self.section_name} - Row {self.row_number}"


class ChecklistImage(models.Model):
	"""Stores images for checklist sections"""
	section = models.ForeignKey(ChecklistSection, on_delete=models.CASCADE, related_name="images")
	checklist = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name="images")
	image = models.ImageField(upload_to=checklist_image_upload_path)
	column_position = models.CharField(max_length=5, default='F')  # F, G, H, etc.
	uploaded_at = models.DateTimeField(auto_now_add=True)
	
	class Meta:
		ordering = ['column_position', 'uploaded_at']
	
	def __str__(self):
		return f"Image for Row {self.section.row_number} - Col {self.column_position}"


class DCPowerSystemData(models.Model):
	"""
	Stores DC Power System data (rows 187-193)
	Column AB (merged): field_label
	Column DEF (merged): field_value
	"""
	checklist = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name="dc_power_data")
	row_number = models.IntegerField()
	field_label = models.CharField(max_length=200)  # From Excel column AB (merged)
	field_value = models.TextField(blank=True)  # Goes to Excel column DEF (merged)
	
	class Meta:
		ordering = ['row_number']
		unique_together = ['checklist', 'row_number']
	
	def __str__(self):
		return f"{self.checklist.id} - Row {self.row_number}: {self.field_label}"


class TowerEquipment(models.Model):
	"""
	Stores dynamic tower equipment data
	
	Column Mapping:
	- Model Name: Column AB (merged)
	- Dimension: Column C
	- Height: Column D
	- Azimuth (Antenna/Microwave): Column E
	- Empty Port (FPFH): Column E
	- Sector/Leg: Column F (or EF merged for Radio)
	"""
	EQUIPMENT_TYPES = [
		('ANTENNA', 'Antenna Model'),
		('RADIO', 'Radio Model'),
		('FPFH', 'FPFH'),
		('MICROWAVE', 'Microwave Model'),
	]
	
	OPERATOR_TYPES = [
		('STC', 'STC'),
		('OTHER', 'Other Operator'),
	]
	
	checklist = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name="tower_equipment")
	operator_type = models.CharField(max_length=10, choices=OPERATOR_TYPES)
	equipment_type = models.CharField(max_length=20, choices=EQUIPMENT_TYPES)
	
	# Row tracking
	row_number = models.IntegerField()  # Dynamic row number in Excel
	position_index = models.IntegerField(default=0)  # Order within same equipment type
	
	# Data fields (columns vary by equipment type)
	model_name = models.CharField(max_length=200, blank=True)  # Col AB
	dimension = models.CharField(max_length=100, blank=True)  # Col C
	height = models.CharField(max_length=100, blank=True)  # Col D
	azimuth = models.CharField(max_length=100, blank=True)  # Col E (for Antenna & Microwave)
	empty_port = models.CharField(max_length=100, blank=True)  # Col E (for FPFH)
	sector_or_leg = models.CharField(max_length=100, blank=True)  # Col F or EF
	
	created_at = models.DateTimeField(auto_now_add=True)
	
	class Meta:
		ordering = ['operator_type', 'equipment_type', 'position_index']
	
	def __str__(self):
		return f"{self.operator_type} - {self.equipment_type} - Row {self.row_number}"


class ElectricalData(models.Model):
	"""Stores electrical data (Voltage, Current R/Y/B, Remarks)"""
	checklist = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name="electrical_data")
	row_number = models.IntegerField()
	position_index = models.IntegerField(default=0)
	
	voltage = models.CharField(max_length=100, blank=True)  # Col AB
	current_r = models.CharField(max_length=100, blank=True)  # Col C
	current_y = models.CharField(max_length=100, blank=True)  # Col D
	current_b = models.CharField(max_length=100, blank=True)  # Col E
	remarks = models.TextField(blank=True)  # Col F
	
	created_at = models.DateTimeField(auto_now_add=True)
	
	class Meta:
		ordering = ['position_index']
	
	def __str__(self):
		return f"Electrical Data - Row {self.row_number}"

from .photo_models import PhotoEvidence, PhotoJob, PhotoDraft, PhotoWorkerLease, PhotoObservation, PhotoSearchVector, PhotoSearchResult  # noqa: E402,F401

from .governance_models import ProjectInvitation, GovernanceAudit, GovernanceState  # noqa: E402,F401

from .ai_review_models import ChecklistAIReview  # noqa: E402,F401

from .photo_models import PhotoPlacement  # noqa: E402,F401

from .intake_models import AssignmentIntakeBatch  # noqa: E402,F401
from .revision_models import ChecklistReviewPolicy, SubmissionRevision, RevisionDecision  # noqa: E402,F401
from .roadmap_models import WorkflowTemplateQualification, InspectionFinding, FindingEvent  # noqa: E402,F401

from .work_profile_models import WorkProfile, ProfessionalExperience  # noqa: E402,F401
from .evidence_models import EvidenceAnalysisRecord, EvidenceRuleRelease, EvidenceCorrection, EvidenceCorrectionDecision  # noqa: E402,F401
from .evidence_models import EvidenceReviewBinding  # noqa: E402,F401
from .checklist_import_models import ChecklistImportBatch  # noqa: E402,F401
from .review_route_models import ReviewRoute, ReviewRouteEvent  # noqa: E402,F401
from .survey_processing_models import SurveyDocument, SurveyUploadSession, SurveyProcessingRevision, SurveyProcessingJob, SurveySourceAnalysis, SurveyProcessingResult, SurveyProcessingEvent, SurveyDrawingSet  # noqa: E402,F401
