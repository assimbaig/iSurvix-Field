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
				fields = ['family_id', 'version', 'name', 'definition', 'published', 'client_left_name', 'client_right_name', 'client_left_logo', 'client_right_logo']
				if any(getattr(previous, field) != getattr(self, field) for field in fields):
					raise ValidationError('Published templates are locked. Duplicate this revision to make changes.')
		return super().save(*args, **kwargs)

	def branding(self):
		return {'clients': [
			{'name': self.client_left_name, 'logo': self.client_left_logo.name or ''},
			{'name': self.client_right_name, 'logo': self.client_right_logo.name or ''},
		]}


def project_template_upload_path(instance: "Project", filename: str) -> str:
	slug = instance.name.strip().lower().replace(" ", "-") or "project"
	return f"project_templates/{slug}/{filename}"


class Project(models.Model):
	name = models.CharField(max_length=120, unique=True)
	description = models.TextField(blank=True)
	template_file = models.FileField(upload_to=project_template_upload_path, blank=True, null=True)
	checklist_template = models.ForeignKey(ChecklistTemplate, null=True, blank=True, on_delete=models.PROTECT, related_name='projects')

	def save(self, *args, **kwargs):
		if self.checklist_template_id and not self.checklist_template.published:
			raise ValidationError('Projects may use published checklist revisions only.')
		return super().save(*args, **kwargs)

	def __str__(self) -> str:
		return self.name


class Profile(models.Model):
	class Roles(models.TextChoices):
		ADMIN = 'ADMIN', 'Admin'
		TEAM_LEAD = 'TEAM_LEAD', 'Team Leader'
		ENGINEER = 'ENGINEER', 'Engineer'

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

	def __str__(self) -> str:
		return f"{self.user.username} ({self.get_role_display()})"


class Checklist(models.Model):
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
	remark_data = models.JSONField(default=dict, blank=True)
	image_data = models.JSONField(default=dict, blank=True)
	template_copy = models.FileField(upload_to="checklists/", blank=True, null=True)
	checklist_template = models.ForeignKey(ChecklistTemplate, null=True, blank=True, on_delete=models.PROTECT, related_name='checklists')
	schema_snapshot = models.JSONField(default=dict, blank=True)
	branding_snapshot = models.JSONField(default=dict, blank=True)
	section_approvals = models.JSONField(default=dict, blank=True)
	review_history = models.JSONField(default=list, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def save(self, *args, **kwargs):
		if self._state.adding and self.project_id:
			template = self.checklist_template or self.project.checklist_template
			if template:
				if not template.published:
					raise ValidationError('Only a published checklist template can be assigned to a survey.')
				self.checklist_template = template
				self.schema_snapshot = deepcopy(template.definition)
				self.branding_snapshot = deepcopy(template.branding())
		return super().save(*args, **kwargs)

	def __str__(self) -> str:
		return f"{self.user.username} - {self.project.name} - {self.site_id or self.id}"

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
