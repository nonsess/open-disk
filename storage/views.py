from django.urls import reverse
from django.contrib import messages
from urllib.parse import quote, unquote
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect

from storage.models import StoredFile
from storage.services import StorageService


@login_required
def file_list(request: HttpRequest) -> HttpResponse:
    raw_path = request.GET.get('path', '')
    current_path = unquote(raw_path).lstrip('/') if raw_path else ''
    
    files, folders, breadcrumbs = StorageService.get_folder_contents(
        user=request.user,
        current_path=current_path
    )
    
    current_folder_name = ""
    if current_path:
        parts = current_path.split('/')
        current_folder_name = parts[-1] if parts else ""

    context = {
        'files': files,
        'folders': folders,
        'current_path': current_path,
        'breadcrumbs': breadcrumbs,
        'current_folder_name': current_folder_name,
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
    
    if not success:
        messages.error(request, message)
    
    return _redirect_to_path(path)


@login_required
def upload_file(request: HttpRequest) -> HttpResponse:
    if request.method != 'POST':
        return render(request, 'storage/upload.html')
    
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
        
    if errors:
        error_display = "; ".join(errors[:5])
        if len(errors) > 5:
            error_display += f" ... и ещё {len(errors) - 5} ошибок"
        
        messages.error(
            request,
            f"Ошибки при загрузке {len(errors)} файл(ов): {error_display}"
        )
    
    return redirect('file_list')
    

@login_required
def download_file(request: HttpRequest, pk: int) -> HttpResponseRedirect:
    file_obj = get_object_or_404(StoredFile, pk=pk, owner=request.user)
    return redirect(file_obj.file.url)


@login_required
def delete_file(request: HttpRequest, pk: int) -> HttpResponseRedirect:
    if request.method != 'POST':
        return redirect('file_list')
    
    success, message = StorageService.delete_file(request.user, pk)
    
    if not success:
        messages.error(request, message)
    
    return redirect('file_list')


@login_required
def delete_folder(request: HttpRequest) -> HttpResponseRedirect:
    if request.method != 'POST':
        return redirect('file_list')
    
    path = request.POST.get('path', '').strip()

    if not path:
        messages.error(request, "Не указана папка для удаления.")
        return redirect('file_list')

    success, message, redirect_path = StorageService.delete_folder(
        user=request.user,
        folder_path=path
    )
    
    if not success:
        messages.error(request, message)
    
    return _redirect_to_path(redirect_path)     

def _redirect_to_path(path: str) -> HttpResponseRedirect:
    if path:
        encoded_path = quote(path)
        return redirect(f"{reverse('file_list')}?path={encoded_path}")
    return redirect('file_list')
