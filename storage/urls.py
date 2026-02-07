from django.urls import path
from . import views

urlpatterns = [
    path('', views.file_list, name='file_list'),
    path('upload/', views.upload_file, name='upload_file'),

    path('download/<int:pk>/', views.download_file, name='download_file'),
    path('delete/<int:pk>/', views.delete_file, name='delete_file'),

    path('folder/create/', views.create_folder, name='create_folder'),
    path('folder/delete/', views.delete_folder, name='delete_folder'),
]