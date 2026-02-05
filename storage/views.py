from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404


from storage.models import StoredFile

@login_required
def file_list(request):
    files = StoredFile.objects.filter(owner=request.user).order_by('-uploaded_at')
    return render(request, 'storage/file_list.html', {'files': files})

@login_required
def upload_file(request):
    if request.method == 'POST':
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            messages.error(request, "Файл не выбран.")
            return render(request, 'storage/upload.html')

        stored_file = StoredFile(
            owner=request.user,
            original_name=uploaded_file.name,
            size=uploaded_file.size,
            mime_type=uploaded_file.content_type or 'application/octet-stream'
        )
        stored_file.file = uploaded_file
        stored_file.save()

        print("Storage class:", stored_file.file.storage.__class__)

        messages.success(request, f"Файл успешно загружен! {stored_file.file.storage.__class__}")
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