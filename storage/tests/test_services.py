from django.test import TestCase
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from storage.models import Folder, StoredFile
from storage.services import StorageService


class StorageServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_get_folder_contents(self):
        folder = Folder.objects.create(owner=self.user, name='Test')

        test_file = SimpleUploadedFile(
            name='test.txt',
            content=b"x",
            content_type='text/plain'
        )

        file = StoredFile.objects.create(
            owner=self.user,
            folder=folder,
            original_name='test.txt',
            file=test_file,
        )

        files, folders, breadcrumbs, current_folder = StorageService.get_folder_contents(
            self.user, 
            'Test'
        )

        self.assertEqual(len(files), 1)
        self.assertEqual(len(folders), 0)
        
        self.assertEqual(len(breadcrumbs), 2)
        self.assertEqual(breadcrumbs[0]['name'], 'Главная')
        self.assertEqual(breadcrumbs[1]['name'], 'Test')
        self.assertEqual(breadcrumbs[1]['path'], 'Test')

        self.assertEqual(current_folder, folder)

        self.assertEqual(files[0].id, file.id)
        self.assertEqual(files[0].display_name, 'test')
    
    def test_get_folder_contents_root(self):
        test_file = SimpleUploadedFile('file.txt', b'Content', 'text/plain')
        StoredFile.objects.create(
            owner=self.user,
            original_name='file.txt',
            file=test_file
        )
        
        files, folders, breadcrumbs, current_folder = StorageService.get_folder_contents(
            self.user
        )
        
        self.assertEqual(len(files), 1)
        self.assertIsNone(current_folder)
        self.assertEqual(len(breadcrumbs), 1)
    
    def test_delete_folder(self):
        parent_folder = Folder.objects.create(
            owner=self.user,
            name='ParentFolder'
        )
        parent_folder_id = parent_folder.id

        test_parent_file = SimpleUploadedFile(
            name='file1.txt',
            content=b"x",
            content_type='text/plain'
        )

        file_in_parent_dir = StoredFile.objects.create(
            owner=self.user,
            folder=parent_folder,
            original_name='file1.txt',
            file=test_parent_file,
        )
        file_in_parent_dir_id = file_in_parent_dir.id

        children_folder = Folder.objects.create(
            owner=self.user,
            name='ChildFolder',
            parent=parent_folder
        )
        children_folder_id = children_folder.id

        test_child_file = SimpleUploadedFile(
            name='file2.txt',
            content=b"x",
            content_type='text/plain'
        )

        file_in_child_dir = StoredFile.objects.create(
            owner=self.user,
            folder=children_folder,
            original_name='file2.txt',
            file=test_child_file
        )
        file_in_child_dir_id = file_in_child_dir.id

        success, message, redirect_path = StorageService.delete_folder(
            self.user,
            parent_folder_id
        )

        self.assertTrue(success)
        self.assertIn('ParentFolder', message)
        self.assertEqual(redirect_path, '')
        
        self.assertFalse(Folder.objects.filter(id=parent_folder_id).exists())
        self.assertFalse(Folder.objects.filter(id=children_folder_id).exists())

        self.assertFalse(StoredFile.objects.filter(id=file_in_parent_dir_id).exists())
        self.assertFalse(StoredFile.objects.filter(id=file_in_child_dir_id).exists())

    def test_delete_folder_only_deletes_owner_files(self):
        folder_user1 = Folder.objects.create(owner=self.user, name='Folder1')
        
        file_user1 = StoredFile.objects.create(
            owner=self.user,
            folder=folder_user1,
            original_name='file.txt',
            file=SimpleUploadedFile('file.txt', b'Content', 'text/plain')
        )
        
        other_user = User.objects.create_user(username='other', password='pass123')
        
        folder_user2 = Folder.objects.create(owner=other_user, name='Folder2')
        
        file_user2 = StoredFile.objects.create(
            owner=other_user,
            folder=folder_user2,
            original_name='file2.txt',
            file=SimpleUploadedFile('file2.txt', b'Content', 'text/plain')
        )
        
        StorageService.delete_folder(self.user, folder_user1.id)
        
        self.assertFalse(StoredFile.objects.filter(id=file_user1.id).exists())
        
        self.assertTrue(StoredFile.objects.filter(id=file_user2.id).exists())
    
    def test_upload_files_creates_nested_folders(self):
        file1 = SimpleUploadedFile(
            name='readme.txt',
            content=b'Important notes',
            content_type='text/plain'
        )
        
        file2 = SimpleUploadedFile(
            name='screenshot.png',
            content=b'\x89PNG\r\n\x1a\n',  # Minimal PNG
            content_type='image/png'
        )
        
        uploaded_count, errors = StorageService.upload_files(
            user=self.user,
            files=[file1, file2],
            relative_paths=[
                'readme.txt',
                'Projects/Website/screenshot.png'
            ]
        )
        
        self.assertEqual(uploaded_count, 2)
        self.assertEqual(errors, [])
        
        self.assertEqual(StoredFile.objects.filter(owner=self.user).count(), 2)
        
        self.assertTrue(Folder.objects.filter(owner=self.user, name='Projects').exists())
        self.assertTrue(Folder.objects.filter(owner=self.user, name='Website').exists())
        
        website_folder = Folder.objects.get(owner=self.user, name='Website')
        self.assertEqual(website_folder.parent.name, 'Projects')
        
        readme = StoredFile.objects.get(owner=self.user, display_name='readme')
        self.assertIsNone(readme.folder)
        
        screenshot = StoredFile.objects.get(owner=self.user, display_name='screenshot')
        self.assertEqual(screenshot.folder.name, 'Website')

    def test_create_folder(self):
        success, message, folder = StorageService.create_folder(
            user=self.user,
            name="Dir"
        )
        
        self.assertTrue(success)
        self.assertEqual(folder.name, 'Dir')
        self.assertIsNone(folder.parent)
        self.assertEqual(folder.owner, self.user)

        self.assertTrue(Folder.objects.filter(owner=self.user, name='Dir').exists())

        success_duplicate, message_duplicate, folder_duplicate = StorageService.create_folder(
            user=self.user,
            name="Dir"
        )

        self.assertFalse(success_duplicate)
        self.assertIsNone(folder_duplicate)
        self.assertIn("уже существует", message_duplicate)
        self.assertEqual(Folder.objects.filter(owner=self.user, name='Dir').count(), 1)
    
    def test_search_files(self):
        for filename in ['document.pdf', 'photo.jpg', 'document_backup.pdf', 'presentation.pptx']:
            test_file = SimpleUploadedFile(
                name=filename,
                content=b'Test content',
                content_type='application/octet-stream'
            )
            StoredFile.objects.create(
                owner=self.user,
                original_name=filename,
                file=test_file
            )
        
        results = StorageService.search_files(self.user, 'document')

        self.assertTrue(len(results), 2)
        
        self.assertTrue(all('document' in f.display_name.lower() for f in results))
        
        self.assertEqual(results[0].display_name, 'document')
        self.assertEqual(results[1].display_name, 'document_backup')

        results_upper = StorageService.search_files(self.user, 'DOCUMENT')
        results_mixed = StorageService.search_files(self.user, 'Document')

        self.assertEqual(len(results_upper), 2)
        self.assertEqual(len(results_mixed), 2)

        results_partial = StorageService.search_files(self.user, 'doc')
        self.assertEqual(len(results_partial), 2)

        results_empty = StorageService.search_files(self.user, 'nothing')
        self.assertEqual(len(results_empty), 0)
    
    def test_search_file_only_onwer(self):
        other_user = User.objects.create_user(username='other', password='pass123')

        other_file = SimpleUploadedFile('secret.pdf', b'Secret', 'application/pdf')
        StoredFile.objects.create(owner=other_user, original_name='secret.pdf', file=other_file)

        results = StorageService.search_files(self.user, 'secret')
        self.assertEqual(len(results), 0)
    
    def test_rename_folder(self):
        folder = Folder.objects.create(owner=self.user, name='OldName')
        folder_id = folder.id
        
        success, message, updated_folder = StorageService.rename_folder(
            user=self.user,
            folder_id=folder_id,
            new_name='NewName'
        )
        
        self.assertTrue(success)
        self.assertIn('NewName', message)
        
        folder.refresh_from_db()
        self.assertEqual(folder.name, 'NewName')
        
        self.assertTrue(Folder.objects.filter(id=folder_id, name='NewName').exists())
    
    def test_rename_folder_duplicate_name(self):
        Folder.objects.create(owner=self.user, name='Folder1')
        folder2 = Folder.objects.create(owner=self.user, name='Folder2')
        
        success, message, updated_folder = StorageService.rename_folder(
            user=self.user,
            folder_id=folder2.id,
            new_name='Folder1'
        )
        
        self.assertFalse(success)
        self.assertIn('уже существует', message)
        
        folder2.refresh_from_db()
        self.assertEqual(folder2.name, 'Folder2')
    
    def test_rename_folder_not_found(self):
        success, message, folder = StorageService.rename_folder(
            user=self.user,
            folder_id=99999,  # error ID
            new_name='NewName'
        )
        
        self.assertFalse(success)
        self.assertIsNone(folder)
        self.assertIn('не найдена', message)
    
    def test_rename_file(self):
        test_file = SimpleUploadedFile(
            name='oldname.txt',
            content=b'Test content',
            content_type='text/plain'
        )
        
        file_obj = StoredFile.objects.create(
            owner=self.user,
            original_name='oldname.txt',
            file=test_file
        )
        file_id = file_obj.id
        
        success, message, updated_file = StorageService.rename_file(
            user=self.user,
            file_id=file_id,
            new_name='newname'
        )
        
        self.assertTrue(success)
        self.assertIn('newname', message)
        
        file_obj.refresh_from_db()
        self.assertEqual(file_obj.display_name, 'newname')
        
        self.assertTrue(StoredFile.objects.filter(id=file_id, display_name='newname').exists())
    
    def test_rename_file_duplicate_name(self):
        file1 = SimpleUploadedFile('file1.txt', b'Content1', 'text/plain')
        file2 = SimpleUploadedFile('file2.txt', b'Content2', 'text/plain')
        
        StoredFile.objects.create(
            owner=self.user,
            original_name='file1.txt',
            file=file1
        )
        stored_file2 = StoredFile.objects.create(
            owner=self.user,
            original_name='file2.txt',
            file=file2
        )
        
        success, message, updated_file = StorageService.rename_file(
            user=self.user,
            file_id=stored_file2.id,
            new_name='file1'
        )
        
        self.assertFalse(success)
        self.assertIn('уже существует', message)
        
        stored_file2.refresh_from_db()
        self.assertEqual(stored_file2.display_name, 'file2')
    
    def test_rename_file_invalid_name(self):
        test_file = SimpleUploadedFile('test.txt', b'Content', 'text/plain')
        file_obj = StoredFile.objects.create(
            owner=self.user,
            original_name='test.txt',
            file=test_file
        )
        
        success, message, updated_file = StorageService.rename_file(
            user=self.user,
            file_id=file_obj.id,
            new_name='file/name'
        )
        
        self.assertFalse(success)
        self.assertIn('содержать символы', message)
    
    def test_rename_file_not_found(self):
        success, message, file_obj = StorageService.rename_file(
            user=self.user,
            file_id=99999,  # erorr ID
            new_name='NewName'
        )
        
        self.assertFalse(success)
        self.assertIsNone(file_obj)
        self.assertIn('не найден', message)
    
    def test_delete_file(self):
        test_file = SimpleUploadedFile(
            name='test.txt',
            content=b'Test content',
            content_type='text/plain'
        )
        
        file_obj = StoredFile.objects.create(
            owner=self.user,
            original_name='test.txt',
            file=test_file
        )
        file_id = file_obj.id

        success, message, redirect_path = StorageService.delete_file(
            user=self.user,
            file_id=file_id
        )
        
        self.assertTrue(success)
        self.assertEqual(message, 'Файл удалён')
        self.assertEqual(redirect_path, '')
        
        self.assertFalse(StoredFile.objects.filter(id=file_id).exists())
    
    def test_delete_file_from_folder(self):
        folder = Folder.objects.create(owner=self.user, name='Documents')

        test_file = SimpleUploadedFile('test.txt', b'Content', 'text/plain')
        file_obj = StoredFile.objects.create(
            owner=self.user,
            folder=folder,
            original_name='test.txt',
            file=test_file
        )
        
        success, message, redirect_path = StorageService.delete_file(
            user=self.user,
            file_id=file_obj.id
        )
        
        self.assertEqual(redirect_path, 'Documents')
    
    def test_delete_file_not_found(self):
        success, message, redirect_path = StorageService.delete_file(
            user=self.user,
            file_id=99999  # error ID
        )
        
        self.assertFalse(success)
        self.assertIn('не найден', message)
        self.assertEqual(redirect_path, '')
    
    def test_delete_file_other_user(self):
        other_user = User.objects.create_user(username='other', password='pass123')
        
        test_file = SimpleUploadedFile('secret.txt', b'Secret', 'text/plain')
        file_obj = StoredFile.objects.create(
            owner=other_user,
            original_name='secret.txt',
            file=test_file
        )
        file_id = file_obj.id
        
        success, message, redirect_path = StorageService.delete_file(
            user=self.user,
            file_id=file_id
        )
        
        self.assertFalse(success)
        
        self.assertTrue(StoredFile.objects.filter(id=file_id).exists())