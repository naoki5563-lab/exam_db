from django.urls import include, path


urlpatterns = [
    path("", include("db_browser.urls")),
]
