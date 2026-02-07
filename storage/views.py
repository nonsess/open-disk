import os
from django.db import IntegrityError
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404
from urllib.parse import quote, unquote

from django.urls import reverse

from storage.models import Folder, StoredFile


@login_required
def file_list(request):
    current_path = request.GET.get('path', '')
    if current_path:
        current_path = unquote(current_path).lstrip('/')

    if current_path:
        files = StoredFile.objects.filter(owner=request.user, path=current_path).order_by('original_name')
    else:
        files = StoredFile.objects.filter(owner=request.user, path='').order_by('original_name')

    if current_path:
        folders = Folder.objects.filter(owner=request.user, path=current_path).order_by('name')
    else:
        folders = Folder.objects.filter(owner=request.user, path='').order_by('name')

    breadcrumbs = [{'name': 'Главная', 'path': ''}]
    if current_path:
        parts = current_path.split('/')
        accumulated = ''
        for part in parts:
            if accumulated:
                accumulated += '/' + part
            else:
                accumulated = part
            breadcrumbs.append({'name': part, 'path': accumulated})

    context = {
        'files': files,
        'folders': folders,
        'current_path': current_path,
        'breadcrumbs': breadcrumbs,
    }
    return render(request, 'storage/file_list.html', context)

@login_required
def create_folder(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        path = request.POST.get('path', '').strip()
        
        if not name:
            messages.error(request, "Имя папки не может быть пустым.")
            return redirect('file_list')
        
        folder = Folder(owner=request.user, name=name, path=path)
        try:
            folder.save()
            messages.success(request, f"Папка '{name}' создана.")
        except IntegrityError:
            messages.error(request, f"Папка с таким названием существует.")

    if path:
        return redirect(f"{reverse('file_list')}?path={quote(path)}")
    return redirect('file_list')

@login_required
def upload_file(request):
    if request.method == 'POST':
        files = request.FILES.getlist('file')
        relative_paths = request.POST.getlist('relative_path')

        if not files:
            messages.error(request, "Файл(ы) не выбраны.")
            return render(request, 'storage/upload.html')

        if len(files) != len(relative_paths):
            messages.error(request, "Ошибка при загрузке структуры папок.")
            return render(request, 'storage/upload.html')

        folder_paths = set()

        for uploaded_file, rel_path in zip(files, relative_paths):
            folder_path = os.path.dirname(rel_path)
            file_name = os.path.basename(rel_path)

            if folder_path:
                parts = folder_path.split('/')
                accumulated = ''
                for part in parts:
                    if accumulated:
                        accumulated += '/' + part
                    else:
                        accumulated = part
                    folder_paths.add(accumulated)

            stored_file = StoredFile(
                owner=request.user,
                original_name=file_name,
                size=uploaded_file.size,
                mime_type=uploaded_file.content_type or 'application/octet-stream',
                path=folder_path
            )
            stored_file.save()
            
            full_path = f"user-{request.user.id}-files/{rel_path}"
            stored_file.file.save(full_path, uploaded_file, save=True)

        for full_folder_path in folder_paths:
            if '/' in full_folder_path:
                parent_path = '/'.join(full_folder_path.split('/')[:-1])
                folder_name = full_folder_path.split('/')[-1]
            else:
                parent_path = ''
                folder_name = full_folder_path

            Folder.objects.get_or_create(
                owner=request.user,
                path=parent_path,
                name=folder_name
            )

        messages.success(request, f"Загружено {len(files)} файл(ов)!")
        return redirect('file_list')
    
    return render(request, 'storage/upload.html')

@login_required
def download_file(request, pk):
    file_obj = get_object_or_404(StoredFile, pk=pk, owner=request.user)
    return redirect(file_obj.file.url)

@login_required
def delete_file(request, pk):
    if request.method == 'POST':
        file_obj = get_object_or_404(StoredFile, pk=pk, owner=request.user)
        file_obj.file.delete(save=False)
        file_obj.delete()
        messages.success(request, "Файл удалён.")
    return redirect('file_list')