from django.shortcuts import render
import django
import rest_framework


def landing_page(request):
    """Render the beautiful landing page with API links"""
    context = {
        'django_version': django.get_version(),
        'drf_version': rest_framework.__version__,
    }
    return render(request, 'landing.html', context)


def api_docs(request):
    """Render the API documentation page"""
    return render(request, 'api_docs.html')
