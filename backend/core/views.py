from django.shortcuts import render


def business_lunches_page(request):
    return render(request, "core/business_lunches.html")


def banquets_page(request):
    return render(request, "core/banquets.html")


def catering_page(request):
    return render(request, "core/catering.html")