# OpenDisk — облачное файловое хранилище

OpenDisk - это веб-приложение для хранения и управления файлами, построенное на Django. Поддерживает вложенную структуру папок, загрузку и скачивание файлов, поиск и базовые операции с файловой системой.

## Технологии

[![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![MinIO](https://img.shields.io/badge/MinIO-FF6F3F?style=for-the-badge&logo=minio&logoColor=white)](https://min.io/)
[![Redis](https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)

## Локальный запуск

1. Убедитесь, что установлены **Docker** и **Docker Compose**.
2. Склонируйте репозиторий:
   ```bash
   git clone https://github.com/nonsess/open-disk.git
   cd open-disk
   ```
3. Создайте файл `.env` на основе `.env.example` и укажите свои значения (если нужно).
4. Запустите приложение:
   ```bash
   docker compose up --build
   ```
5. Приложение будет доступно по адресу: [http://localhost:8000](http://localhost:8000)

## Запуск тестов

Тесты написаны с использованием стандартного фреймворка `unittest` и запускаются внутри контейнера:

```bash
# Запустить все тесты
docker-compose exec web python manage.py test

# Запустить тесты конкретного приложения
docker-compose exec web python manage.py test storage
docker-compose exec web python manage.py test accounts

# Запустить с подробным выводом
docker-compose exec web python manage.py test -v 2
```

Для проверки покрытия кода тестами:

```bash
# Установите coverage (если ещё не установлено)
docker-compose exec web pip install coverage

# Запустите тесты с покрытием
docker-compose exec web coverage run --source='.' manage.py test

# Посмотрите отчёт
docker-compose exec web coverage report -m
```

## Структура проекта

- `accounts`: регистрация и аутентификация пользователей
- `storage`: основная логика работы с файлами и папками
- `config`: настройки Django
- `templates`: базовые шаблоны интерфейса

## Возможности

- Регистрация и вход в систему
- Создание, переименование и удаление папок
- Загрузка файлов с сохранением структуры каталогов
- Поиск файлов по имени
- Скачивание файлов
- Валидация имён файлов и папок
- Защита от несанкционированного доступа к чужим данным

## Безопасность

- Пользователи могут работать только со своими файлами и папками
- Все операции с файлами проходят через авторизованные представления
- Имена файлов и папок валидируются на наличие недопустимых символов
- Пароли хранятся в зашифрованном виде

## Лицензия

Проект распространяется под лицензией MIT.