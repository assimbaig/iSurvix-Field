"""Reviewed release highlights, versioned with the application source.

Maintain this content with each user-facing release. The installed immutable
source identity, not this editorial identifier, controls hosted acknowledgements.
Local development uses NOTE_ID as an explicit stable fallback; no Git is run.
"""
NOTE_ID='account-recovery-exports-v1-3-beta'
LOCAL_RELEASE_KEY='local-'+NOTE_ID
NOTES={
    'note_id':NOTE_ID,
    'title':"What's new in iField - V1.3 Beta",
    'version':'1.3',
    'date':'2026-11-07',
    'changes':(
        'Reset your password using a short-lived, single-use link sent to your registered email address.',
        'Invitation and action emails include iField branding, a signature and an account-safety disclaimer.',
        'Update notices show the release version; platform administrators can view retained release history.',
        'Prepare permission-scoped Excel exports in the background and download them from My exports.',
        'Exports include standard column guidance, dated filenames and a personal preparation history.',
        'Existing company boundaries, original evidence and human approval controls remain in place.',
    ),
}
