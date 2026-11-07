from django.urls import path
from . import account_recovery_views as views

urlpatterns=[
    path('account/password-reset/',views.request_password_reset,name='account_password_reset'),
    path('account/password-reset/sent/',views.reset_done,name='account_password_reset_done'),
    path('account/password-reset/complete/',views.reset_complete,name='account_password_reset_complete'),
    path('account/password-reset/<uuid:request_id>/<str:token>/',views.confirm_password_reset,name='account_password_reset_confirm'),
]
