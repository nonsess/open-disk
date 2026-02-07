from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from urllib.parse import quote, unquote

from storage.models import Folder, StoredFile
from storage.services import StorageService


@login_required
def file_list(request: HttpRequest) -> HttpResponse:
    raw_path = request.GET.get('path', '')
    current_path = unquote(raw_path).lstrip('/') if raw_path else ''
    
    files, folders, breadcrumbs = StorageService.get_folder_contents(
        user=request.user,
        current_path=current_path
    )
    
    context = {
        'files': files,
        'folders': folders,
        'current_path': current_path,
        'breadcrumbs': breadcrumbs,
    }
    
    return render(request, 'storage/file_list.html', context)


@login_required
def create_folder(request: HttpRequest) -> HttpResponse:
    if request.method != 'POST':
        return redirect('file_list')
    
    name = request.POST.get('name', '').strip()
    path = request.POST.get('path', '').strip()
    
    success, message, _ = StorageService.create_folder(
        user=request.user,
        name=name,
        path=path
    )
    
    if success:
        messages.success(request, message)
    else:
        messages.error(request, message)
    
    return _redirect_to_path(path)


@login_required
def upload_file(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        files = request.FILES.getlist('file')
        relative_paths = request.POST.getlist('relative_path')
        
        error_message = StorageService.validate_upload_data(files, relative_paths)
        if error_message:
            messages.error(request, error_message)
            return render(request, 'storage/upload.html')
        
        uploaded_count, errors = StorageService.upload_files(
            user=request.user,
            files=files,
            relative_paths=relative_paths
        )
        
        if uploaded_count > 0:
            messages.success(
                request, 
                f"Успешно загружено {uploaded_count} файл(ов)!"
            )
        
        if errors:
            error_display = "; ".join(errors[:5])
            if len(errors) > 5:
                error_display += f" ... и ещё {len(errors) - 5} ошибок"
            
            messages.error(
                request,
                f"Ошибки при загрузке {len(errors)} файл(ов): {error_display}"
            )
        
        return redirect('file_list')
    
    return render(request, 'storage/upload.html')


@login_required
def download_file(request: HttpRequest, pk: int) -> HttpResponseRedirect:
    file_obj = get_object_or_404(StoredFile, pk=pk, owner=request.user)
    return redirect(file_obj.file.url)


@login_required
def delete_file(request: HttpRequest, pk: int) -> HttpResponseRedirect:
    if request.method != 'POST':
        return redirect('file_list')
    
    success, message = StorageService.delete_file(request.user, pk)
    
    if success:
        messages.success(request, message)
    else:
        messages.error(request, message)
    
    return redirect('file_list')


@login_required
def folder_detail(request: HttpRequest, pk: int) -> HttpResponse:
    folder = get_object_or_404(Folder, pk=pk, owner=request.user)
    
    files, folders, breadcrumbs = StorageService.get_folder_contents(
        user=request.user,
        current_path=folder.full_path
    )
    
    context = {
        'folder': folder,
        'files': files,
        'folders': folders,
        'current_path': folder.full_path,
        'breadcrumbs': breadcrumbs,
    }
    
    return render(request, 'storage/folder_detail.html', context)


@login_required
def delete_folder(request: HttpRequest, pk: int) -> HttpResponseRedirect:
    if request.method != 'POST':
        return redirect('file_list')
    
    folder = get_object_or_404(Folder, pk=pk, owner=request.user)
    
    parent_path = folder.path
    
    try:
        files_to_delete = StoredFile.objects.filter(
            owner=request.user,
            path__startswith=folder.full_path
        )
        
        for file_obj in files_to_delete:
            file_obj.file.delete(save=False)
        
        files_to_delete.delete()
        
        Folder.objects.filter(
            owner=request.user,
            path__startswith=folder.full_path
        ).delete()
        
        folder.delete()
        
        messages.success(request, f"Папка '{folder.name}' и всё её содержимое удалены.")
        
    except Exception as e:
        messages.error(request, f"Ошибка при удалении папки: {str(e)}")
    
    return _redirect_to_path(parent_path)


def public_download(request: HttpRequest, uuid_str: str) -> HttpResponseRedirect:
    try:
        from uuid import UUID
        file_uuid = UUID(uuid_str)
        
        file_obj = get_object_or_404(
            StoredFile, 
            public_link=file_uuid,
            is_public=True
        )
        
        return redirect(file_obj.file.url)
        
    except ValueError:
        messages.error(request, "Некорректная ссылка.")
        return redirect('file_list')


def _redirect_to_path(path: str) -> HttpResponseRedirect:
    if path:
        encoded_path = quote(path)
        return redirect(f"{reverse('file_list')}?path={encoded_path}")
    return redirect('file_list')
