from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.contrib import auth


class SignupViewTests(TestCase):
    def setUp(self):
        self.client = Client()
    
    def test_signup_success(self):
        response = self.client.post(reverse('signup'), {
            'username': 'newuser',
            'password1': 'securepass123',
            'password2': 'securepass123'
        }, follow=True)
        
        self.assertRedirects(response, reverse('file_list'))
        
        self.assertTrue(User.objects.filter(username='newuser').exists())
    
    def test_signup_password_mismatch(self):
        response = self.client.post(reverse('signup'), {
            'username': 'testuser',
            'password1': 'password123',
            'password2': 'password456'
        })
        
        self.assertFalse(User.objects.filter(username='testuser').exists())
        self.assertFormError(response.context['form'], 'password2', 'The two password fields didn’t match.')
    
    def test_signup_duplicate_username(self):
        User.objects.create_user(username='existing', password='pass123')
        
        response = self.client.post(reverse('signup'), {
            'username': 'existing',
            'password1': 'newpass123',
            'password2': 'newpass123'
        })
        
        self.assertFormError(response.context['form'], 'username', 'A user with that username already exists.')
    
    def test_signup_weak_password(self):
        response = self.client.post(reverse('signup'), {
            'username': 'weakuser',
            'password1': '123',
            'password2': '123'
        })
        
        password_errors = response.context['form'].errors.get('password2', [])
    
        expected_errors = [
            'This password is too short. It must contain at least 8 characters.',
            'This password is too common.',
            'This password is entirely numeric.'
        ]
        
        for error in expected_errors:
            self.assertIn(error, password_errors)

class LoginViewTests(TestCase):    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_login_success(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'testpass123'
        }, follow=True)
        
        self.assertRedirects(response, reverse('file_list'))
        user = auth.get_user(self.client)
        self.assertTrue(user.is_authenticated)
    
    def test_login_wrong_password(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        
        user = auth.get_user(self.client)
        self.assertFalse(user.is_authenticated)
        self.assertContains(response, 'Неверное имя пользователя или пароль.')
    
    def test_login_empty_fields(self):
        response = self.client.post(reverse('login'), {
            'username': '',
            'password': ''
        })
        
        self.assertFormError(response.context['form'], 'username', 'This field is required.')
        self.assertFormError(response.context['form'], 'password', 'This field is required.')


class LogoutViewTests(TestCase):    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.client.login(username='testuser', password='testpass123')
    
    def test_logout_success(self):
        user = auth.get_user(self.client)
        self.assertTrue(user.is_authenticated)
        
        response = self.client.post(reverse('logout'), follow=True)
        
        self.assertRedirects(response, reverse('login'))
        user = auth.get_user(self.client)
        self.assertFalse(user.is_authenticated)


class AuthenticationRequiredTests(TestCase):    
    def test_file_list_requires_login(self):
        response = self.client.get(reverse('file_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)