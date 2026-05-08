from django.urls import path

from . import views


app_name = "db_browser"

urlpatterns = [
    path("", views.index, name="index"),
    path("search/", views.global_search, name="global_search"),
    path("passages/<str:pk>/read/", views.passage_read, name="passage_read"),
    path("passages/<str:pk>/", views.passage_detail, name="passage_detail"),
    path("tables/<str:table>/<str:pk>/", views.row_detail, name="row_detail"),
]
