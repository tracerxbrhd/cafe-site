# Deploy On Aeza VPS

Этот проект теперь готов к выкладке через production stack:

- `docker-compose.prod.yml`
- `backend/.env.production.example`
- `deploy/nginx/default.conf`
- `backend/entrypoint.prod.sh`
- `backend/gunicorn.conf.py`

## 1. Что подготовить заранее

- VPS на `Ubuntu 24.04 LTS`
- SSH-доступ
- публичный IP
- отдельный домен, если он уже есть

## 1.1. Чем подключаться к серверу с Windows

Рекомендуемый вариант:

- `Windows Terminal` или обычный `PowerShell` для SSH-команд
- `WinSCP` для удобной загрузки файлов на сервер

Если в Windows уже есть встроенный SSH-клиент, подключение выглядит так:

```powershell
ssh root@SERVER_IP
```

Если SSH в системе не установлен, проверьте наличие `OpenSSH Client` в дополнительных компонентах Windows.

Если вам удобнее полностью графический клиент, можно использовать `PuTTY`, но для этого проекта проще держать основной поток через `Windows Terminal + ssh`.

## 1.2. Что запросить или проверить в панели Aeza

До начала работ убедитесь, что у вас есть:

- `IP` сервера
- пользователь для входа, чаще всего `root`
- пароль `root` или заранее добавленный SSH-ключ
- выбранная ОС `Ubuntu 24.04 LTS`

Если сервер только что создан, обычно удобнее войти по паролю, а уже потом настроить SSH-ключ и отдельного пользователя.

Если домена пока нет, можно сначала запускать по IP.
В этом случае:

- `DJANGO_ALLOWED_HOSTS` должен включать IP
- `DJANGO_CSRF_TRUSTED_ORIGINS` должен включать `http://IP`
- `DJANGO_SECURE_SSL_REDIRECT=0`
- `DJANGO_SESSION_COOKIE_SECURE=0`
- `DJANGO_CSRF_COOKIE_SECURE=0`

## 2. Обязательно перевыпустить секреты

Перед production нужно заменить все секреты, которые уже использовались локально:

- `DJANGO_SECRET_KEY`
- `DB_PASSWORD`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET`
- `YOOKASSA_SECRET_KEY`

Если ключ или токен уже публиковался в чатах, логах, скриншотах или старых `.env`, считайте его скомпрометированным.

## 3. Установка Docker на сервер

Пример для Ubuntu:

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable docker
sudo systemctl start docker
```

Если хотите запускать `docker` без `sudo`, добавьте своего пользователя в группу:

```bash
sudo usermod -aG docker $USER
```

После этого нужно переподключиться по SSH.

## 3.1. Базовая подготовка сервера

После первого входа рекомендую сразу сделать минимум:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl ufw
sudo timedatectl set-timezone Europe/Samara
```

Если входите под `root`, `sudo` можно не писать.

## 3.2. Открытие нужных портов

Минимальный набор для первого запуска:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

Порт `5432` открывать наружу не нужно.

## 4. Заливка проекта на сервер

Пример:

```bash
git clone <your-repository-url> cafe-site
cd cafe-site
```

Если git пока не используется для деплоя, можно залить архивом или через `scp`.

Если будете загружать проект с Windows вручную, самый простой путь такой:

1. Откройте `WinSCP`
2. Подключитесь по `SFTP` к `SERVER_IP`
3. Войдите как `root` или другой пользователь
4. Загрузите папку проекта, например в `/opt/cafe-site`
5. Далее все команды выполняйте уже по SSH в этой папке

Итоговая рабочая директория в примерах ниже:

```bash
cd /opt/cafe-site
```

## 5. Создание production env

Скопируйте шаблон:

```bash
cp backend/.env.production.example backend/.env.production
```

Заполните `backend/.env.production`.

Минимальный вариант для первого запуска по IP:

```env
DJANGO_SECRET_KEY=very-long-random-secret
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=SERVER_IP
DJANGO_CSRF_TRUSTED_ORIGINS=http://SERVER_IP

DJANGO_SECURE_SSL_REDIRECT=0
DJANGO_SESSION_COOKIE_SECURE=0
DJANGO_CSRF_COOKIE_SECURE=0
DJANGO_SECURE_HSTS_SECONDS=0

DB_NAME=cafe_skazka
DB_USER=cafe_user
DB_PASSWORD=strong-password
DB_HOST=db
DB_PORT=5432

TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
TELEGRAM_NOTIFICATIONS_ENABLED=0
TELEGRAM_WEBHOOK_SECRET=random-secret
TELEGRAM_POLLING_ENABLED=1

YOOKASSA_SHOP_ID=
YOOKASSA_SECRET_KEY=
```

## 6. Первый запуск production stack

Запускать нужно именно так, чтобы `docker compose` брал переменные из production env:

```bash
docker compose --env-file backend/.env.production -f docker-compose.prod.yml up -d --build
```

Проверить контейнеры:

```bash
docker compose --env-file backend/.env.production -f docker-compose.prod.yml ps
```

Проверить health endpoint:

```bash
curl http://SERVER_IP/healthz/
```

Если ответ такой:

```json
{"ok":true,"database":"available"}
```

значит стек поднялся корректно.

### Telegram-кнопки статусов на проде

Сейчас проект поддерживает быстрый рабочий режим без домена и `HTTPS`:

- отдельный контейнер `bot`
- long polling к Telegram API
- кнопки статусов в Telegram работают даже если сайт открыт только по `http://SERVER_IP`

Для этого в `backend/.env.production` должно быть:

```env
TELEGRAM_NOTIFICATIONS_ENABLED=1
TELEGRAM_POLLING_ENABLED=1
```

Проверить состояние bot-контейнера:

```bash
docker compose --env-file backend/.env.production -f docker-compose.prod.yml ps
docker compose --env-file backend/.env.production -f docker-compose.prod.yml logs -f bot
```

## 7. Создание superuser

```bash
docker compose --env-file backend/.env.production -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

## 8. Как перенести текущую локальную БД на сервер

Рекомендуемый способ: не копировать docker volume напрямую, а сделать дамп PostgreSQL и восстановить его на сервере.

Это самый безопасный и переносимый вариант.

### 8.1. Создать дамп на локальной машине

Из корня проекта на локальной машине:

```powershell
docker compose exec -T db pg_dump -U cafe_user -d cafe_skazka --clean --if-exists > cafe_skazka_local.sql
```

В результате рядом с проектом появится файл `cafe_skazka_local.sql`.

### 8.2. Загрузить дамп на сервер

Через `WinSCP` загрузите файл, например, в:

```bash
/opt/cafe-site/cafe_skazka_local.sql
```

### 8.3. Остановить веб-контейнер перед восстановлением

На сервере:

```bash
cd /opt/cafe-site
docker compose --env-file backend/.env.production -f docker-compose.prod.yml stop web
```

### 8.4. Восстановить дамп в PostgreSQL на сервере

Если production-стек уже поднят, выполните:

```bash
docker compose --env-file backend/.env.production -f docker-compose.prod.yml exec -T db \
  sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < cafe_skazka_local.sql
```

После этого серверная база станет копией локальной.

### 8.5. Снова запустить приложение

```bash
docker compose --env-file backend/.env.production -f docker-compose.prod.yml up -d
```

### 8.6. Проверить, что данные на месте

```bash
docker compose --env-file backend/.env.production -f docker-compose.prod.yml exec web python manage.py showmigrations
curl http://SERVER_IP/healthz/
```

Потом проверьте сайт и админку в браузере.

### 8.7. Если на сайте есть загруженные изображения

Одной базы недостаточно, если у вас уже есть файлы в `media`.

Тогда нужно ещё перенести содержимое локальной папки `backend/media` в server volume `media_data`.
Самый простой практический путь:

1. Локально скачать или скопировать содержимое `backend/media`
2. Загрузить эти файлы на сервер во временную папку, например `/opt/cafe-site/media-import`
3. Из директории `/opt/cafe-site` скопировать их в контейнер:

```bash
docker cp ./media-import/. $(docker compose --env-file backend/.env.production -f docker-compose.prod.yml ps -q web):/app/media/
```

Если захотите, этот шаг лучше сделать отдельно и аккуратно, чтобы не потерять уже загруженные файлы.

## 9. Полезные команды

Логи:

```bash
docker compose --env-file backend/.env.production -f docker-compose.prod.yml logs -f
```

Логи только веба:

```bash
docker compose --env-file backend/.env.production -f docker-compose.prod.yml logs -f web
```

Логи Telegram polling:

```bash
docker compose --env-file backend/.env.production -f docker-compose.prod.yml logs -f bot
```

Проверка deploy-настроек Django:

```bash
docker compose --env-file backend/.env.production -f docker-compose.prod.yml exec web \
  python manage.py check --deploy --settings=config.settings.prod
```

Перезапуск после изменения `.env.production` или конфигов:

```bash
docker compose --env-file backend/.env.production -f docker-compose.prod.yml up -d --build
```

Остановка:

```bash
docker compose --env-file backend/.env.production -f docker-compose.prod.yml down
```

Быстрое обновление после изменений в коде:

```bash
cd /opt/cafe-site
git pull
sh ./deploy.prod.sh
```

Если вы обновляете проект не через `git`, а через `WinSCP`, тогда после загрузки файлов достаточно:

```bash
cd /opt/cafe-site
sh ./deploy.prod.sh
```

## 10. Когда появится домен

После привязки домена обновите `backend/.env.production`:

```env
DJANGO_ALLOWED_HOSTS=example.com,www.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://example.com,https://www.example.com
```

После настройки HTTPS включите:

```env
DJANGO_SECURE_SSL_REDIRECT=1
DJANGO_SESSION_COOKIE_SECURE=1
DJANGO_CSRF_COOKIE_SECURE=1
DJANGO_SECURE_HSTS_SECONDS=31536000
DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=1
DJANGO_SECURE_HSTS_PRELOAD=1
```

Важно:

- сначала убедитесь, что HTTPS уже реально работает
- только потом включайте HSTS

## 11. SSL

Текущий `nginx`-конфиг рассчитан на старт по `HTTP`.
Для боевого домена следующим шагом нужно:

1. прописать DNS на IP сервера
2. выпустить сертификат Let's Encrypt
3. добавить `listen 443 ssl;` и пути к сертификатам в `deploy/nginx/default.conf`
4. включить secure-настройки Django

Практически это лучше делать в два этапа:

1. Сначала запустить сайт по `http://SERVER_IP`
2. Проверить заказ, админку, YooKassa, загрузку статики и медиа
3. Потом привязать домен и включить `HTTPS`
4. Только после этого включать `DJANGO_SECURE_SSL_REDIRECT=1` и `HSTS`

## 12. Бэкапы

Минимум для production:

- ежедневный дамп PostgreSQL
- резервная копия каталога с `media`
- хранение бэкапов вне самой VPS

Пример дампа:

```bash
docker compose --env-file backend/.env.production -f docker-compose.prod.yml exec -T db \
  sh -lc 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > backup_$(date +%F).sql
```

## 13. Переезд на другой хостинг позже

Чтобы переезд прошёл спокойно:

- держите production env отдельно от кода
- храните бэкапы базы и `media`
- не меняйте структуру volume без необходимости
- заранее сохраните список DNS-записей, переменных окружения и webhook URL

При переезде на новый хостинг обычно меняются только:

- IP сервера
- DNS
- SSL
- иногда `DJANGO_ALLOWED_HOSTS` и `DJANGO_CSRF_TRUSTED_ORIGINS`

Сами контейнеры, база и код могут остаться теми же.

## 13.1. Автозапуск сайта после перезагрузки сервера

В production compose уже указано:

- `restart: unless-stopped` у `web`
- `restart: unless-stopped` у `bot`
- `restart: unless-stopped` у `nginx`
- `restart: unless-stopped` у `db`

Если на сервере выполнено:

```bash
systemctl enable docker
```

то после `reboot` Docker сам поднимет контейнеры снова.

Проверка после перезагрузки:

```bash
docker compose --env-file backend/.env.production -f docker-compose.prod.yml ps
```

## 14. Быстрый чеклист первого запуска

Если нужен самый короткий маршрут, то он такой:

1. Подключиться к серверу по SSH:

```powershell
ssh root@SERVER_IP
```

2. Установить Docker и `git`
3. Загрузить проект в `/opt/cafe-site`
4. Создать `backend/.env.production`
5. Запустить:

```bash
cd /opt/cafe-site
docker compose --env-file backend/.env.production -f docker-compose.prod.yml up -d --build
```

6. Проверить:

```bash
docker compose --env-file backend/.env.production -f docker-compose.prod.yml ps
curl http://SERVER_IP/healthz/
```

7. Создать админа:

```bash
docker compose --env-file backend/.env.production -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

8. Открыть в браузере:

- `http://SERVER_IP/`
- `http://SERVER_IP/admin/`

## 15. Что делать, если что-то не запускается

Почти всегда первым делом полезно посмотреть:

```bash
docker compose --env-file backend/.env.production -f docker-compose.prod.yml logs -f web
docker compose --env-file backend/.env.production -f docker-compose.prod.yml logs -f nginx
docker compose --env-file backend/.env.production -f docker-compose.prod.yml logs -f db
```

Частые причины:

- ошибка в `backend/.env.production`
- занятый `80` порт
- не указан `DJANGO_ALLOWED_HOSTS`
- старые или неверные секреты
- проект загружен не в ту директорию
