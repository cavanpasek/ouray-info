from django.urls import path
from .views import home, business_detail, contact

urlpatterns = [
    path("", home, name="home"),
    path("contact/", contact, name="contact"),
    path("business/<slug:slug>/", business_detail, name="business_detail"),
]
