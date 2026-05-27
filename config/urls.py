from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

admin.site.site_header = 'Value Intelligence Library Admin'
admin.site.site_title = 'VIL Admin'
admin.site.index_title = 'Knowledge Management'

urlpatterns = [
    path('admin/', admin.site.urls),
    path(
        'login/',
        auth_views.LoginView.as_view(template_name='registration/login.html'),
        name='login',
    ),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('dashboard.urls')),
    path('library/', include('library.urls')),
    path('taxonomy/', include('taxonomy.urls')),
    path('knowledge/', include('knowledge.urls')),
    path('ai-extraction/', include('ai_extraction.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
