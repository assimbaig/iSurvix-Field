"""Immutable human release notes, separate from per-user dismissal preferences."""
from django.db import models


class InstalledRelease(models.Model):
    release_key=models.CharField(max_length=80,unique=True)
    version=models.CharField(max_length=32)
    title=models.CharField(max_length=180)
    release_date=models.DateField()
    changes=models.JSONField(default=list)
    first_seen_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering=['-first_seen_at','-pk']
