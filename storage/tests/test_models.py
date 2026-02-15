from django.test import TestCase
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from storage.models import Folder, StoredFile


class FolderModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_root_folder(self):
        folder = Folder.objects.create(
            owner=self.user,
            name='Documents'
        )
        
        self.assertEqual(folder.name, 'Documents')
        self.assertIsNone(folder.parent)
        self.assertEqual(folder.owner, self.user)
    
    def test_create_nested_folder(self):
        parent = Folder.objects.create(
            owner=self.user,
            name='Parent'
        )
        
        child = Folder.objects.create(
            owner=self.user,
            name='Child',
            parent=parent
        )
        
        self.assertEqual(child.parent, parent)
        self.assertEqual(parent.children.count(), 1)
    
    def test_unique_constraint(self):
        Folder.objects.create(
            owner=self.user,
            name='Documents'
        )
        
        with self.assertRaises(Exception):  # IntegrityError
            Folder.objects.create(
                owner=self.user,
                name='Documents'
            )
    
    def test_full_path_property(self):
        root = Folder.objects.create(owner=self.user, name='Root')
        child = Folder.objects.create(owner=self.user, name='Child', parent=root)
        grandchild = Folder.objects.create(owner=self.user, name='Grandchild', parent=child)
        
        self.assertEqual(root.full_path, 'Root')
        self.assertEqual(child.full_path, 'Root/Child')
        self.assertEqual(grandchild.full_path, 'Root/Child/Grandchild')
    
    def test_circular_reference_prevention(self):
        folder1 = Folder.objects.create(owner=self.user, name='Folder1')
        folder2 = Folder.objects.create(owner=self.user, name='Folder2', parent=folder1)
        
        folder1.parent = folder2
        
        with self.assertRaises(Exception):  # ValidationError
            folder1.save()
    
    def test_rename_folder(self):
        folder = Folder.objects.create(owner=self.user, name='OldName')
        
        result = folder.rename('NewName')
        
        self.assertEqual(result['old_name'], 'OldName')
        self.assertEqual(result['new_name'], 'NewName')
        folder.refresh_from_db()
        self.assertEqual(folder.name, 'NewName')
    
    def test_delete_folder_with_files(self):
        folder = Folder.objects.create(owner=self.user, name='ToDelete')
        
        test_file = SimpleUploadedFile(
            name='test.txt',
            content=b'Test content',
            content_type='text/plain'
        )
        
        stored_file = StoredFile.objects.create(
            owner=self.user,
            folder=folder,
            original_name='test.txt',
            file=test_file
        )
        
        folder_id = folder.id
        stored_file_id = stored_file.id
        folder.delete()
        
        self.assertFalse(Folder.objects.filter(id=folder_id).exists())
        self.assertFalse(StoredFile.objects.filter(id=stored_file_id).exists())


class StoredFileModelTests(TestCase):    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.folder = Folder.objects.create(
            owner=self.user,
            name='TestFolder'
        )
    
    def test_create_file(self):
        test_file = SimpleUploadedFile(
            name='test.txt',
            content=b'Test content',
            content_type='text/plain'
        )
        
        stored_file = StoredFile.objects.create(
            owner=self.user,
            folder=self.folder,
            original_name='test.txt',
            file=test_file
        )
        
        self.assertEqual(stored_file.owner, self.user)
        self.assertEqual(stored_file.folder, self.folder)
        self.assertEqual(stored_file.original_name, 'test.txt')
        self.assertEqual(stored_file.display_name, 'test')
        self.assertEqual(stored_file.extension, 'txt')
        self.assertEqual(stored_file.size, 12)
    
    def test_human_size_property(self):
        test_cases = [
            (b'', "0 Б"),
            (b'x' * 512, "512.0 Б"),
            (b'x' * 1024, "1.0 КБ"),
            (b'x' * (1024 * 1024), "1.0 МБ"),
            (b'x' * (1024 * 1024 * 1024), "1.0 ГБ"),
        ]
        
        for content, expected in test_cases:
            test_file = SimpleUploadedFile(
                name='test.txt',
                content=content,
                content_type='text/plain'
            )
            
            stored_file = StoredFile.objects.create(
                owner=self.user,
                original_name='test.txt',
                file=test_file
            )
            
            stored_file.size = len(content)
            stored_file.save()
            
            self.assertEqual(stored_file.human_size, expected)
    
    def test_file_type_property(self):
        test_cases = [
            ('application/pdf', 'pdf'),
            ('image/jpeg', 'image'),
            ('image/png', 'image'),
            ('application/zip', 'archive'),
            ('application/msword', 'document'),
            ('text/plain', 'text'),
        ]
        
        for mime_type, expected_type in test_cases:
            test_file = SimpleUploadedFile(
                name='test.txt',
                content=b'Test',
                content_type=mime_type
            )
            
            stored_file = StoredFile.objects.create(
                owner=self.user,
                original_name='test.txt',
                file=test_file,
                mime_type=mime_type
            )
            
            self.assertEqual(stored_file.file_type, expected_type)
    
    def test_unique_filename_constraint(self):
        test_file1 = SimpleUploadedFile(
            name='test.txt',
            content=b'Test1',
            content_type='text/plain'
        )
        
        StoredFile.objects.create(
            owner=self.user,
            folder=self.folder,
            original_name='test.txt',
            file=test_file1
        )
        
        test_file2 = SimpleUploadedFile(
            name='test.txt',
            content=b'Test2',
            content_type='text/plain'
        )
        
        with self.assertRaises(Exception):  # IntegrityError
            StoredFile.objects.create(
                owner=self.user,
                folder=self.folder,
                original_name='test.txt',
                file=test_file2
            )
    
    def test_rename_file(self):
        test_file = SimpleUploadedFile(
            name='oldname.txt',
            content=b'Test',
            content_type='text/plain'
        )
        
        file_obj = StoredFile.objects.create(
            owner=self.user,
            folder=self.folder,
            original_name='oldname.txt',
            file=test_file
        )
        
        result = file_obj.rename('newname')
        
        self.assertEqual(result['old_name'], 'oldname')
        self.assertEqual(result['new_name'], 'newname')
        file_obj.refresh_from_db()
        self.assertEqual(file_obj.display_name, 'newname')
    
    def test_filename_validation(self):
            invalid_names = [
                ('', 'Имя файла не может быть пустым'),
                ('   ', 'Имя файла не может состоять только из пробелов'),
                ('file\\name.txt', '\\'),
                ('file:name.txt', ':'),
                ('file*.txt', '*'),
                ('file?.txt', '?'),
                ('file".txt', '"'),
                ('file<.txt', '<'),
                ('file>.txt', '>'),
                ('file|.txt', '|'),
                ('file/name.txt', 'содержать символы /'),
                ('a' * 256 + '.txt', 'превышать 255 символов'),
            ]
            
            for invalid_name, expected_error in invalid_names:
                with self.assertRaises(Exception) as context:
                    StoredFile._validate_filename(invalid_name)
                
                error_msg = str(context.exception)
                self.assertIn(expected_error, error_msg)
    
    def test_valid_filename(self):
        valid_names = [
            'document.pdf',
            'my file.txt',
            'файл_на_русском.pdf',
            'file-name.pdf',
            'file_name.pdf',
            'file.name.pdf',
        ]
        
        for valid_name in valid_names:
            StoredFile._validate_filename(valid_name)