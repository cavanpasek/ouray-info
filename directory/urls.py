from django.urls import path
from .views import home, business_detail

urlpatterns = [
    path("", home, name="home"),
    path("business/<slug:slug>/", business_detail, name="business_detail"),
]
