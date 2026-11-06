"""Account preferences for a single installed release, separate from field work."""
from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.db import models
from django.dispatch import receiver


SESSION_KEY='_ifield_release_notice'


class ReleaseNoticeAcknowledgement(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,
        related_name='release_notice_acknowledgements')
    release_key=models.CharField(max_length=80)
    acknowledged_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints=[models.UniqueConstraint(fields=['user','release_key'],name='unique_user_release_notice_ack')]


@receiver(user_logged_in,dispatch_uid='core.release_notice_new_login')
def clear_login_notice_state(sender,request,user,**kwargs):
    # Account-level acknowledgements remain. An unchecked choice lasts for this
    # login only, including when authentication cycles an existing session key.
    if request is not None and hasattr(request,'session'):
        request.session.pop(SESSION_KEY,None)
