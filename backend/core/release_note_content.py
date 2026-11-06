"""Reviewed release highlights, versioned with the application source.

Maintain this content with each user-facing release. The installed immutable
source identity, not this editorial identifier, controls hosted acknowledgements.
Local development uses NOTE_ID as an explicit stable fallback; no Git is run.
"""
NOTE_ID='company-overview-20261106'
LOCAL_RELEASE_KEY='local-'+NOTE_ID
NOTES={
    'note_id':NOTE_ID,
    'title':"What's new in iField",
    'date':'2026-11-06',
    'changes':(
        'Company Admins have a compact company overview with scoped site, photo, activity, project, client and people totals.',
        'New Project, New Task, New Client and Invite User are easier to reach; existing permissions and review rules remain in place.',
        'Project summaries and current review-stage counts use saved application records. Historical stages that cannot be verified are identified separately.',
        'Release notices can be remembered for the current update. A future deployed version will show its own notice.',
    ),
}
