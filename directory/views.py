from django.shortcuts import render, get_object_or_404
from .models import Business

def home(request):
    businesses = Business.objects.all()
    return render(request, "home.html", {"businesses": businesses})

def business_detail(request, slug):
    b = get_object_or_404(Business, slug=slug)
    return render(request, "business_detail.html", {"b": b})
