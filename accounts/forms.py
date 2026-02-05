from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User


class CustomUserCreationForm(UserCreationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'w-full px-2 py-1 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gold focus:outline-none',
            'placeholder': 'Имя пользователя'
        })
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-2 py-1 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gold focus:outline-none',
            'placeholder': 'Пароль'
        })
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-2 py-1 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gold focus:outline-none',
            'placeholder': 'Подтвердите пароль'
        })
    )

    class Meta:
        model = User
        fields = ("username", "password1", "password2")

class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'w-full px-2 py-1 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gold focus:outline-none',
            'placeholder': 'Имя пользователя'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-2 py-1 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gold focus:outline-none',
            'placeholder': 'Пароль'
        })
    )