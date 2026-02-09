from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from urllib.parse import quote

from storage.models import Folder, StoredFile
from storage.services import StorageService


def _redirect_to_path(path: str) -> HttpResponseRedirect:
    url = reverse('file_list')
    if path:
        url += f"?path={quote(path)}"
    return redirect(url)


@login_required
def file_list(request: HttpRequest) -> HttpResponse:
    current_path = request.GET.get('path', '').strip()
    
    files, folders, breadcrumbs, current_folder = StorageService.get_folder_contents(
        request.user, current_path
    )
    
    current_folder_name = ""
    if current_folder:
        current_folder_name = current_folder.name
    
    return render(request, 'storage/file_list.html', {
        'files': files,
        'folders': folders,
        'breadcrumbs': breadcrumbs,
        'current_path': current_path,
        'current_folder_name': current_folder_name,
        'current_folder': current_folder,
    })


@login_required
def upload_file(request: HttpRequest) -> HttpResponse:
    current_path = request.GET.get('path', '').strip()
    current_folder = None
    current_folder_name = ""
    
    if current_path:
        current_folder = Folder.find_by_path(request.user, current_path)
        if current_folder:
            current_folder_name = current_folder.name
    
    if request.method == 'POST':
        post_current_path = request.POST.get('current_path', '').strip()
        if post_current_path:
            current_path = post_current_path
            current_folder = Folder.find_by_path(request.user, current_path)
            if current_folder:
                current_folder_name = current_folder.name
        
        files = request.FILES.getlist('files')
        
        relative_paths = []
        for file_obj in files:
            if current_folder and current_folder.full_path:
                full_path = f"{current_folder.full_path}/{file_obj.name}"
            else:
                full_path = file_obj.name
            relative_paths.append(full_path)
        
        error = StorageService.validate_upload_data(files, relative_paths)
        if error:
            messages.error(request, error)
            return _redirect_to_path(current_path)
        
        uploaded_count, errors = StorageService.upload_files(
            request.user, files, relative_paths
        )
                
        for error in errors:
            messages.error(request, error)
        
        return _redirect_to_path(current_path)
    
    return render(request, 'storage/upload.html', {
        'current_path': current_path,
        'current_folder': current_folder,
        'current_folder_name': current_folder_name,
    })


@login_required
def download_file(request: HttpRequest, pk: int) -> HttpResponse:
    file_obj = get_object_or_404(StoredFile, pk=pk, owner=request.user)
    
    response = HttpResponse(file_obj.file, content_type=file_obj.mime_type)
    response['Content-Disposition'] = f'attachment; filename="{file_obj.original_name}"'
    return response


@login_required
def search_file(request: HttpRequest) -> HttpResponse:
    query = request.GET.get('query', '').strip()

    files = []
    if query:
        files = StorageService.search_files(request.user, query)
    
    return render(request, 'storage/search.html', {
        'query': query,
        'files': files,
    })


@login_required
def delete_file(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method == 'POST':
        success, message = StorageService.delete_file(request.user, pk)
        
        if not success:
            messages.error(request, message)

    return redirect('file_list')


@login_required
def rename_file(request: HttpRequest) -> HttpResponse:
    if request.method != 'POST':
        return redirect('file_list')
    
    file_id = request.POST.get('file_id', '').strip()
    new_name = request.POST.get('new_name', '').strip()
    
    if not file_id or not new_name:
        messages.error(request, 'Не указаны необходимые параметры')
        return redirect('file_list')
    
    try:
        file_id_int = int(file_id)
    except ValueError:
        messages.error(request, 'Неверный ID файла')
        return redirect('file_list')
    
    success, message, file_obj = StorageService.rename_file(
        user=request.user,
        file_id=file_id_int,
        new_name=new_name
    )
    
    if not success:
        messages.error(request, message)
    
    if file_obj and file_obj.folder:
        return _redirect_to_path(file_obj.folder.full_path)
    return redirect('file_list')


@login_required
def create_folder(request: HttpRequest) -> HttpResponse:
    if request.method != 'POST':
        return redirect('file_list')
    
    name = request.POST.get('name', '').strip()
    parent_path = request.POST.get('path', '').strip()
    
    if not name:
        messages.error(request, "Имя папки не может быть пустым")
        return _redirect_to_path(parent_path)
    
    success, message, folder = StorageService.create_folder(
        user=request.user,
        name=name,
        parent_path=parent_path
    )
    
    if not success:
        messages.error(request, message)
    
    return _redirect_to_path(parent_path)


@login_required
def rename_folder(request: HttpRequest) -> HttpResponse:
    if request.method != 'POST':
        return redirect('file_list')
    
    folder_id = request.POST.get('folder_id', '').strip()
    new_name = request.POST.get('new_name', '').strip()
    
    if not folder_id or not new_name:
        messages.error(request, 'Не указаны необходимые параметры')
        return redirect('file_list')
    
    try:
        folder_id_int = int(folder_id)
    except ValueError:
        messages.error(request, 'Неверный ID папки')
        return redirect('file_list')
    
    success, message, folder = StorageService.rename_folder(
        user=request.user,
        folder_id=folder_id_int,
        new_name=new_name
    )
    
    if success:
        if folder and folder.parent:
            return _redirect_to_path(folder.parent.full_path)
        return redirect('file_list')
    else:
        messages.error(request, message)
        if folder:
            return _redirect_to_path(folder.full_path)
        return redirect('file_list')


@login_required
def delete_folder(request: HttpRequest) -> HttpResponse:
    if request.method != 'POST':
        return redirect('file_list')
    
    folder_id = request.POST.get('folder_id', '').strip()
    
    if not folder_id:
        messages.error(request, 'Ошибка. Папки не существует')
        return redirect('file_list')
    
    folder_id_int = int(folder_id)
    
    success, message, redirect_path = StorageService.delete_folder(
        user=request.user,
        folder_id=folder_id_int
    )
    
    if not success:
        messages.error(request, message)
    
    return _redirect_to_path(redirect_path)