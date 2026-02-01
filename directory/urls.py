from django.urls import path
from .views import home, business_detail, contact, contact_success

urlpatterns = [
    path("", home, name="home"),
    path("contact/", contact, name="contact"),
    path("contact/success/", contact_success, name="contact_success"),
    path("business/<slug:slug>/", business_detail, name="business_detail"),
]
