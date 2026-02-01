from django import forms
from django.contrib import admin

from .models import Business


class BusinessAdminForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = "__all__"
        help_texts = {
            "logo_image": "Upload a square PNG logo for the top-right card spot.",
            "hero_image": "Upload a wide JPG/PNG hero image for the detail page background.",
        }

@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    form = BusinessAdminForm
    list_display = ("name", "category", "website")
    search_fields = ("name", "category")
    prepopulated_fields = {"slug": ("name",)}
    fields = (
        "name",
        "slug",
        "category",
        "description",
        "website",
        "phone",
        "address",
        "logo_image",
        "hero_image",
    )