from django import forms
from django.contrib import admin
from django.core.validators import FileExtensionValidator

from .models import Business

ALLOWED_IMAGE_EXTENSIONS = ["webp", "jpg", "jpeg", "png"]


class BusinessAdminForm(forms.ModelForm):
    hero_image = forms.ImageField(
        required=False,
        validators=[FileExtensionValidator(allowed_extensions=ALLOWED_IMAGE_EXTENSIONS)],
    )
    logo_image = forms.ImageField(
        required=False,
        validators=[FileExtensionValidator(allowed_extensions=ALLOWED_IMAGE_EXTENSIONS)],
    )

    class Meta:
        model = Business
        fields = "__all__"

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