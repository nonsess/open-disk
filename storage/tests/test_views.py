from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from storage.models import Folder, StoredFile


class FileListViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')

    def test_file_list_anonymous_redirect(self):
        self.client.logout()
        response = self.client.get(reverse('file_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_file_list_authenticated(self):
        response = self.client.get(reverse('file_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'storage/file_list.html')
    
    def test_file_list_with_data(self):
        folder = Folder.objects.create(owner=self.user, name='TestFolder')
        test_file = SimpleUploadedFile('test.txt', b'Content', 'text/plain')
        StoredFile.objects.create(owner=self.user, folder=folder, original_name='test.txt', file=test_file)
        
        response = self.client.get(reverse('file_list'))
        
        self.assertIn('files', response.context)
        self.assertIn('folders', response.context)
        self.assertIn('breadcrumbs', response.context)
        self.assertEqual(len(response.context['folders']), 1)
        self.assertEqual(len(response.context['files']), 0)
        
        response2 = self.client.get(reverse('file_list'), {
            'path': 'TestFolder'
        })

        self.assertIn('files', response2.context)
        self.assertEqual(len(response2.context['files']), 1)


class CreateFolderViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')

    def test_create_folder_success(self):
        self.client.post(reverse('create_folder'), {
            'name': 'NewFolder',
            'path': ''
        }, follow=True)
        
        self.assertTrue(Folder.objects.filter(owner=self.user, name='NewFolder').exists())
        
    def test_create_folder_empty_name(self):
        response = self.client.post(reverse('create_folder'), {
            'name': '',
            'path': ''
        }, follow=True)
        
        messages = list(response.context['messages'])
        self.assertTrue(any('не может быть пустым' in str(m) for m in messages))
    
    def test_create_folder_duplicate(self):
        Folder.objects.create(owner=self.user, name='Existing')
        
        response = self.client.post(reverse('create_folder'), {
            'name': 'Existing',
            'path': ''
        }, follow=True)
        
        messages = list(response.context['messages'])
        self.assertTrue(any('уже существует' in str(m) for m in messages))


class DeleteFolderViewTests(TestCase):    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
    
    def test_delete_folder_success(self):
        folder = Folder.objects.create(owner=self.user, name='ToDelete')
        folder_id = folder.id
        
        response = self.client.post(reverse('delete_folder'), {
            'folder_id': folder_id
        })
        
        self.assertEqual(response.status_code, 302)

        self.assertFalse(Folder.objects.filter(id=folder_id).exists())
    
    def test_delete_folder_not_found(self):
        response = self.client.post(reverse('delete_folder'), {
            'folder_id': 99999
        }, follow=True)
        
        messages = list(response.context['messages'])
        self.assertTrue(any('не найдена' in str(m) for m in messages))


class UploadFileViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
    
    def test_upload_file_form_display(self):
        response = self.client.get(reverse('upload_file'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'storage/upload.html')
    
    def test_upload_file_success(self):
        test_file = SimpleUploadedFile(
            'document.pdf',
            b'%PDF-1.4 test content',
            'application/pdf'
        )
        
        response = self.client.post(reverse('upload_file'), {
            'files': [test_file],
            'file_paths': ['document.pdf'],
            'current_path': ''
        }, follow=True)
        
        self.assertEqual(StoredFile.objects.filter(owner=self.user).count(), 1)
        
        messages = list(response.context['messages'])
        error_messages = [m for m in messages if 'Ошибка' in str(m) or 'error' in str(m).lower()]
        self.assertEqual(len(error_messages), 0)
    
    def test_upload_file_to_folder(self):
        test_file = SimpleUploadedFile('image.jpg', b'\xff\xd8\xff', 'image/jpeg')
        
        response = self.client.post(reverse('upload_file'), {
            'files': [test_file],
            'file_paths': ['Photos/image.jpg'],
            'current_path': ''
        }, follow=True)
        
        self.assertTrue(Folder.objects.filter(owner=self.user, name='Photos').exists())
        
        file_obj = StoredFile.objects.get(owner=self.user, display_name='image')
        self.assertEqual(file_obj.folder.name, 'Photos')


class DownloadFileViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
    
    def test_download_file_owner(self):
        test_file = SimpleUploadedFile('test.txt', b'File content', 'text/plain')
        file_obj = StoredFile.objects.create(
            owner=self.user,
            original_name='test.txt',
            file=test_file
        )
        
        response = self.client.get(reverse('download_file', args=[file_obj.id]))
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain')
        self.assertIn('attachment; filename="test"', response['Content-Disposition'])
        self.assertEqual(response.content, b'File content')
    
    def test_download_file_other_user(self):
        other_user = User.objects.create_user(username='other', password='pass123')
        test_file = SimpleUploadedFile('secret.txt', b'Secret', 'text/plain')
        file_obj = StoredFile.objects.create(
            owner=other_user,
            original_name='secret.txt',
            file=test_file
        )
        
        response = self.client.get(reverse('download_file', args=[file_obj.id]))
        
        self.assertEqual(response.status_code, 404)
    
    def test_download_file_not_found(self):
        response = self.client.get(reverse('download_file', args=[99999]))
        self.assertEqual(response.status_code, 404)


class SearchFileViewTests(TestCase):    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
    
    def test_search_files(self):
        for name in ['document.pdf', 'photo.jpg', 'document_backup.pdf']:
            test_file = SimpleUploadedFile(name, b'Test', 'application/octet-stream')
            StoredFile.objects.create(owner=self.user, original_name=name, file=test_file)
        
        response = self.client.get(reverse('search_file'), {'query': 'document'})
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('files', response.context)
        self.assertEqual(len(response.context['files']), 2)
    
    def test_search_empty_query(self):
        response = self.client.get(reverse('search_file'), {'query': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['files']), 0)


class RenameFileViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
    
    def test_rename_file_success(self):
        test_file = SimpleUploadedFile('old.txt', b'Content', 'text/plain')
        file_obj = StoredFile.objects.create(
            owner=self.user,
            original_name='old.txt',
            file=test_file
        )
        
        self.client.post(reverse('rename_file'), {
            'file_id': file_obj.id,
            'new_name': 'new'
        }, follow=True)
        
        file_obj.refresh_from_db()
        self.assertEqual(file_obj.display_name, 'new')
            
    def test_rename_file_invalid_name(self):
        test_file = SimpleUploadedFile('test.txt', b'Content', 'text/plain')
        file_obj = StoredFile.objects.create(
            owner=self.user,
            original_name='test.txt',
            file=test_file
        )
        
        response = self.client.post(reverse('rename_file'), {
            'file_id': file_obj.id,
            'new_name': 'file/name'
        }, follow=True)
        
        messages = list(response.context['messages'])
        self.assertTrue(any('содержать символы' in str(m) for m in messages))


class RenameFolderViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
    
    def test_rename_folder_success(self):
        folder = Folder.objects.create(owner=self.user, name='OldName')
        
        self.client.post(reverse('rename_folder'), {
            'folder_id': folder.id,
            'new_name': 'NewName'
        }, follow=True)
        
        folder.refresh_from_db()
        self.assertEqual(folder.name, 'NewName')
    
    def test_rename_folder_duplicate(self):
        Folder.objects.create(owner=self.user, name='Existing')
        folder = Folder.objects.create(owner=self.user, name='Target')
        
        response = self.client.post(reverse('rename_folder'), {
            'folder_id': folder.id,
            'new_name': 'Existing'
        }, follow=True)
        
        messages = list(response.context['messages'])
        self.assertTrue(any('уже существует' in str(m) for m in messages))