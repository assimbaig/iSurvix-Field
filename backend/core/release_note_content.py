"""Reviewed release highlights, versioned with the application source.

Maintain this content with each user-facing release. The installed immutable
source identity, not this editorial identifier, controls hosted acknowledgements.
Local development uses NOTE_ID as an explicit stable fallback; no Git is run.
"""
NOTE_ID='superadmin-company-desk-v1-2-beta'
LOCAL_RELEASE_KEY='local-'+NOTE_ID
NOTES={
    'note_id':NOTE_ID,
    'title':"What's new in iField · V1.2 Beta",
    'date':'2026-11-06',
    'changes':(
        'Super Admin has three clear destinations: Dashboard, Companies and System.',
        'Company and application tables show saved records, current status and the next available administrative action.',
        'Company, project, site/task and submission history navigation keeps the selected record in context.',
        'The company onboarding wizard keeps application review, provisioning and Admin invitation as separate steps.',
        'Company Admins can customize action-email subjects and messages using safe placeholders.',
        'Combined daily notification reports support company time zones, configurable cut-off times and recovery of missed business days.',
        'Existing company boundaries, technical approval rules and administrative tools remain in place.',
    ),
}
