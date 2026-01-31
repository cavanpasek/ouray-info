from django.contrib import admin
from .models import Business

@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "website")
    search_fields = ("name", "category")
    prepopulated_fields = {"slug": ("name",)}