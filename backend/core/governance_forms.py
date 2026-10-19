"""Server-constrained governance forms; posted IDs never determine access."""
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db.models import Q
from .models import Project,ChecklistTemplate,Profile,WorkAssignment,Company,Checklist,IndustryCatalog,ClientOrganization
from .access import is_super_admin,role_for,can_access_project,accessible_projects,users_for_project,company_id_for

class ProjectForm(forms.ModelForm):
    industry=forms.ChoiceField(required=False)
    review_layers=forms.TypedChoiceField(choices=[(3,'3 layers - Engineer > QA > Team Lead (closes after approval)'),(4,'4 layers - Engineer > QA > Team Lead > Client decision')],coerce=int,initial=3,label='Approval workflow')
    class Meta:
        model=Project
        fields=['name','description','industry','company','review_layers','checklist_template']
    def __init__(self,*args,actor=None,**kwargs):
        self.actor=actor
        super().__init__(*args,**kwargs)
        self.fields['checklist_template'].queryset=ChecklistTemplate.objects.filter(published=True)
        self.fields['industry'].required=False
        self.fields['industry'].choices=[('', 'Choose an industry'),*IndustryCatalog.objects.filter(is_active=True).values_list('code','name')]
        if actor and role_for(actor)==Profile.Roles.ADMIN:
            from .template_views import template_scope
            company=company_id_for(actor)
            industry=actor.profile.admin_industry
            self.fields['company'].queryset=Company.objects.filter(pk=company)
            self.fields['company'].initial=company
            self.fields['company'].disabled=True
            self.fields['industry'].choices=[(industry.code,industry.name)] if industry else []
            self.fields['industry'].initial=industry.code if industry else ''
            self.fields['industry'].disabled=True
            self.fields['checklist_template'].queryset=template_scope(actor).filter(published=True)
            self.instance.company_id=company
            self.instance.industry=industry.code if industry else ''
            self.instance.administrator=actor
            self.fields['checklist_template'].help_text='Optional now. Create or publish a checklist in the Wizard, then assign it before site work.'
    def clean(self):
        data=super().clean()
        if self.actor and role_for(self.actor)==Profile.Roles.ADMIN:
            industry=getattr(self.actor.profile.admin_industry,'code','')
            for key,expected in [('company',str(company_id_for(self.actor) or '')),('industry',industry)]:
                supplied=self.data.get(key)
                if supplied not in (None,'',expected):self.add_error(key,'Project company and industry come from your Admin account and cannot be changed.')
        return data
    def clean_industry(self):
        code=self.cleaned_data.get('industry') or Project.Industry.TELECOM
        if not IndustryCatalog.objects.filter(code=code,is_active=True).exists():raise forms.ValidationError('Choose an active industry.')
        return code

class IndustryForm(forms.Form):
    code=forms.SlugField(max_length=20,help_text='Editable code; renaming preserves linked industry records and project references.')
    name=forms.CharField(max_length=100)
    description=forms.CharField(max_length=6000,required=False,widget=forms.Textarea,help_text='Describe the industry scope. AI suggestions remain editable until you explicitly save.')
    workflow_family=forms.ChoiceField(choices=[('telecom','Telecom'),('construction','Construction'),('other','Other')],required=False,initial='other',help_text='Choose the technical workflow family when creating an industry. It is fixed after creation.')
    is_active=forms.BooleanField(required=False,initial=True)
    expected_token=forms.CharField(max_length=64,required=False,widget=forms.HiddenInput)
    def __init__(self,*args,instance=None,**kwargs):
        if instance and instance.pk:
            kwargs.setdefault('initial',{key:getattr(instance,key) for key in ['code','name','description','workflow_family','is_active']})
        super().__init__(*args,**kwargs)
        if instance and instance.pk:
            self.fields['workflow_family'].disabled=True
            self.fields['expected_token'].required=True
            self.fields['expected_token'].initial=instance.edit_token
    def clean_workflow_family(self):
        return self.cleaned_data.get('workflow_family') or 'other'


class AdminIndustryForm(forms.Form):
    admin_industry=forms.ModelChoiceField(queryset=IndustryCatalog.objects.filter(is_active=True))

class InvitationForm(forms.Form):
    company=forms.ModelChoiceField(queryset=Company.objects.all(),required=False,label='Admin company (required when no project is selected)')
    admin_industry=forms.ModelChoiceField(queryset=IndustryCatalog.objects.filter(is_active=True),required=False)
    email=forms.EmailField()
    role=forms.ChoiceField()
    project=forms.ModelChoiceField(queryset=Project.objects.none(),required=False,label='Existing project (optional for a new Admin)')
    def __init__(self,*args,actor,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['role'].choices=([(Profile.Roles.ADMIN,'Project Admin')] if is_super_admin(actor) else []) + [(Profile.Roles.ENGINEER,'Engineer'),(Profile.Roles.TEAM_LEAD,'Team Lead'),(Profile.Roles.CLIENT,'Client'),(Profile.Roles.PROJECT_MANAGER,'Project Manager'),(Profile.Roles.QUALITY_ENGINEER,'Quality Engineer')]
        if is_super_admin(actor):self.fields['role'].choices=[choice for choice in self.fields['role'].choices if choice[0]!=Profile.Roles.CLIENT]
        self.fields['project'].queryset=accessible_projects(actor)
        if not is_super_admin(actor):
            self.fields.pop('admin_industry');self.fields.pop('company')
            self.fields['project'].required=True
            self.fields['project'].label='Project'
    def clean(self):
        data=super().clean()
        if data.get('role')==Profile.Roles.ADMIN:
            industry=data.get('admin_industry')
            if not industry:self.add_error('admin_industry','Choose the industry this Admin will manage.')
            elif data.get('project') and data['project'].industry!=industry.code:self.add_error('admin_industry','The Admin industry must match the selected project.')
            if data.get('project') and data['project'].administrator_id:
                self.add_error('project','This project already has an owning Admin. Invite the new Admin with company and industry only, or transfer existing project ownership explicitly.')
            if not data.get('project') and not data.get('company'):
                self.add_error('company','Choose the company this Admin will manage before they create their first project.')
        elif not data.get('project'):
            self.add_error('project','Choose a project for this operational role.')
        if data.get('project'):
            if data.get('company') and data['company'].pk!=data['project'].company_id:
                self.add_error('company','The company must match the selected project.')
            data['company']=data['project'].company
        return data
    def clean_email(self):
        email=self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account already uses this email; manage its existing membership instead.')
        return email

class InvitationAcceptForm(UserCreationForm):
    email=forms.EmailField()
    class Meta(UserCreationForm.Meta):
        model=User
        fields=['username','email']
    def __init__(self,*args,invitation,**kwargs):
        self.invitation=invitation
        super().__init__(*args,**kwargs)
        self.fields['email'].initial=invitation.email
    def clean_email(self):
        email=self.cleaned_data['email'].strip().lower()
        if email!=self.invitation.email.lower():
            raise forms.ValidationError('Use the email address this invitation was issued to.')
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('This email already has an account.')
        return email

class AssignmentForm(forms.Form):
    project=forms.ModelChoiceField(queryset=Project.objects.none())
    engineer=forms.ModelChoiceField(queryset=User.objects.none())
    site_id=forms.CharField(max_length=120)
    latitude=forms.DecimalField(max_digits=10,decimal_places=7,min_value=-90,max_value=90)
    longitude=forms.DecimalField(max_digits=10,decimal_places=7,min_value=-180,max_value=180)
    description=forms.CharField(widget=forms.Textarea,max_length=10000)
    general_info=forms.JSONField(required=False,widget=forms.Textarea,help_text='Optional general-information field IDs and values from the published checklist.')
    workflow_type=forms.ChoiceField(choices=[('','Use project industry default'),*Checklist.WorkflowType.choices],required=False)
    governance_mode=forms.ChoiceField(choices=Checklist.GovernanceMode.choices,required=False,initial='legacy')
    asset_reference=forms.CharField(max_length=200,required=False)
    coordinate_source=forms.CharField(max_length=200,required=False)
    coordinate_crs=forms.CharField(max_length=120,required=False,label='Coordinate datum / CRS')
    quality_reviewer=forms.ModelChoiceField(queryset=User.objects.none(),required=False,label='Assigned Quality Engineer (existing review flow)')
    l2_reviewer=forms.ModelChoiceField(queryset=User.objects.none(),required=False,label='Independent L2 Quality Engineer')
    l3_approver=forms.ModelChoiceField(queryset=User.objects.none(),required=False,label='Independent L3 Team Lead')
    client_review_required=forms.ChoiceField(choices=[('','Use existing project routing (legacy only)'),('required','Client release required'),('not_required','Client release not applicable')],required=False)
    customer_reviewer=forms.ModelChoiceField(queryset=User.objects.none(),required=False,label='Assigned Client reviewer')
    review_reason=forms.CharField(max_length=2000,required=False,widget=forms.Textarea,label='Review assignments and Client applicability reason')
    def __init__(self,*args,actor,**kwargs):
        self.actor=actor
        super().__init__(*args,**kwargs)
        projects=accessible_projects(actor)
        self.fields['project'].queryset=projects
        self.fields['engineer'].queryset=User.objects.filter(pk__in=[user.pk for project in projects for user in users_for_project(project,{Profile.Roles.ENGINEER})]).distinct()
        for key,role in [('quality_reviewer',Profile.Roles.QUALITY_ENGINEER),('l2_reviewer',Profile.Roles.QUALITY_ENGINEER),('l3_approver',Profile.Roles.TEAM_LEAD),('customer_reviewer',Profile.Roles.CLIENT)]:
            self.fields[key].queryset=User.objects.filter(pk__in=[user.pk for project in projects for user in users_for_project(project,{role})]).distinct()
    def clean_site_id(self):
        site=self.cleaned_data['site_id'].strip()
        if WorkAssignment.objects.filter(site_id=site).exists():
            raise forms.ValidationError('This site already has an assignment; update the existing task.')
        return site
    def clean(self):
        data=super().clean()
        project,engineer=data.get('project'),data.get('engineer')
        from .models import Checklist
        data['governance_mode']=data.get('governance_mode') or Checklist.GovernanceMode.LEGACY
        if project:
            if project.review_layers in (3,4):
                data['governance_mode']=Checklist.GovernanceMode.INDEPENDENT
                required=project.review_layers==4
                supplied=data.get('client_review_required')
                if supplied and (supplied=='required')!=required:
                    self.add_error('client_review_required','Client routing is fixed by this project approval workflow.')
                data['client_review_required']='required' if required else 'not_required'
                if not required and data.get('customer_reviewer'):
                    self.add_error('customer_reviewer','A three-layer project does not have a Client approval stage.')
                data['review_reason']=data.get('review_reason') or f'Project-selected {project.review_layers}-layer approval workflow.'
                data['l2_reviewer']=data.get('l2_reviewer') or data.get('quality_reviewer')
            from .industry_service import industry_family
            family=industry_family(project)
            data['workflow_type']=data.get('workflow_type') or (Checklist.WorkflowType.CONSTRUCTION_INSPECTION if family==Project.Industry.CONSTRUCTION else Checklist.WorkflowType.TELECOM_SURVEY)
            workflow=data['workflow_type']
            mode=data['governance_mode']
            expected=Project.Industry.CONSTRUCTION if workflow==Checklist.WorkflowType.CONSTRUCTION_INSPECTION else Project.Industry.TELECOM
            if family!=expected:
                self.add_error('workflow_type','Choose a workflow matching the project industry. Construction survey is outside this release.')
            if workflow!=Checklist.WorkflowType.TELECOM_SURVEY and not data.get('asset_reference'):
                self.add_error('asset_reference','Identify the asset or inspection location.')
            if workflow!=Checklist.WorkflowType.TELECOM_SURVEY and mode!=Checklist.GovernanceMode.INDEPENDENT:
                self.add_error('governance_mode','New inspection workflows require independent L1/L2/L3 review.')
            if mode==Checklist.GovernanceMode.LEGACY:
                quality=data.get('quality_reviewer')
                if not quality:self.add_error('quality_reviewer','Assign a Quality Engineer before the Engineer submits this activity.')
                elif not can_access_project(quality,project):self.add_error('quality_reviewer','Choose an active Quality Engineer from this project.')
            if mode==Checklist.GovernanceMode.INDEPENDENT:
                for key in ['l2_reviewer','l3_approver','client_review_required','review_reason']:
                    if not data.get(key):self.add_error(key,'This is required for independent review.')
                for key in ['l2_reviewer','l3_approver','customer_reviewer']:
                    reviewer=data.get(key)
                    if reviewer and not can_access_project(reviewer,project):self.add_error(key,'Choose an active reviewer from this project.')
                if data.get('client_review_required')=='required' and not data.get('customer_reviewer'):
                    self.add_error('customer_reviewer','Assign the Client responsible for this release.')
                actors=[person.pk for person in [engineer,data.get('l2_reviewer'),data.get('l3_approver'),data.get('customer_reviewer')] if person]
                if len(actors)!=len(set(actors)):self.add_error(None,'Submitter and reviewers must be different people.')
        if project and not project.checklist_template_id:
            self.add_error('project','Assign a published checklist template to this project first.')
        if project and project.checklist_template_id:
            from .standard_checklist_service import validate_standard_project
            try:validate_standard_project(project.checklist_template,project,data.get('workflow_type'))
            except forms.ValidationError as exc:self.add_error('workflow_type',exc)
        if project and engineer and not can_access_project(engineer,project):
            self.add_error('engineer','Choose an engineer from this project.')
        if project and project.checklist_template_id:
            from .field_intake_service import validated_general_info
            try:
                data['general_info']=validated_general_info(project.checklist_template.definition,data.get('general_info') or {})
            except forms.ValidationError as exc:
                self.add_error('general_info',exc)
        return data

class ClientApprovalForm(forms.Form):
    expected_updated_at=forms.CharField(max_length=64)
    expected_review_token=forms.RegexField(regex=r'^[0-9a-f]{64}:[A-Za-z0-9_-]+$',max_length=160)
    decision=forms.ChoiceField(choices=[('approved','Client approved'),('rejected','Client rejected')])
    approver_name=forms.CharField(max_length=160)
    approver_email=forms.EmailField()
    reference=forms.CharField(max_length=2000,required=False,widget=forms.Textarea)

    def clean(self):
        data=super().clean()
        if data.get('decision')=='rejected' and not data.get('reference','').strip():
            self.add_error('reference','Provide the reason for the client rejection.')
        return data

class MaintenanceResetForm(forms.Form):
    typed_confirmation=forms.CharField(label='Type RESET ACCESS')
    password=forms.CharField(widget=forms.PasswordInput,label='Your current password')
    def __init__(self,*args,actor,**kwargs):
        self.actor=actor
        super().__init__(*args,**kwargs)
    def clean_typed_confirmation(self):
        value=self.cleaned_data['typed_confirmation']
        if value!='RESET ACCESS':
            raise forms.ValidationError('Type RESET ACCESS exactly.')
        return value
    def clean_password(self):
        value=self.cleaned_data['password']
        if not self.actor.check_password(value):
            raise forms.ValidationError('Your current password is incorrect.')
        return value


class ProjectAdministratorForm(forms.Form):
    administrator=forms.ModelChoiceField(queryset=User.objects.none(),label='Project administrator')
    def __init__(self,*args,project,**kwargs):
        self.project=project
        super().__init__(*args,**kwargs)
        self.fields['administrator'].queryset=User.objects.filter(is_active=True,is_superuser=False,profile__role=Profile.Roles.ADMIN).filter(Q(profile__company_id=project.company_id)|Q(profile__company__isnull=True,profile__project__company_id=project.company_id)|Q(profile__company__isnull=True,profile__project__isnull=True)).filter(Q(profile__admin_industry__isnull=True)|Q(profile__admin_industry__code=project.industry)).order_by('username')


class CompanyForm(forms.ModelForm):
    class Meta:
        model=Company
        fields=['name','description']

class ProjectCompanyForm(forms.Form):
    company=forms.ModelChoiceField(queryset=Company.objects.all())

class MembershipForm(forms.Form):
    project=forms.ModelChoiceField(queryset=Project.objects.none())
    action=forms.ChoiceField(choices=[('grant','Grant project access'),('revoke','Revoke project access')])
    make_primary=forms.BooleanField(required=False)
    expires_at=forms.DateTimeField(required=False,widget=forms.DateTimeInput(attrs={'type':'datetime-local'}),label='Optional project grant expiry')
    def __init__(self,*args,actor,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['project'].queryset=accessible_projects(actor)


class ClientOrganizationForm(forms.ModelForm):
    class Meta:
        model=ClientOrganization
        fields=['name','description']
    def clean_name(self):
        value=self.cleaned_data['name'].strip()
        if not value:raise forms.ValidationError('Enter a client organization name.')
        return value

class ProjectClientForm(forms.Form):
    client_organization=forms.ModelChoiceField(queryset=ClientOrganization.objects.none())
    def __init__(self,*args,actor,project,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['client_organization'].queryset=ClientOrganization.objects.filter(company_id=company_id_for(actor),industry__code=project.industry)
