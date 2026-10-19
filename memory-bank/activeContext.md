# Active Context: Текущий контекст и статус

## 1. Текущее состояние проекта
Проект NurCRM для сферы услуг (`NurCRM-services`) **успешно выкачен и запущен на боевом стейджинг-сервере `https://stage.nurcrm.kg/`**:
- **Размещение:** сервер `167.233.194.233`, каталог `/opt/nurcrm-services`.
- **Бэкенд:** 11 микросервисов + админ-панель + внутренний Nginx Gateway запущены в Docker Compose (`127.0.0.1:8088`), не конфликтуя с остальными сервисами хоста.
- **Фронтенд (`front-usluga`):** упакован в Docker-контейнер `deploy-frontend-service-1` (Next.js 16 + React 19), работает через внутреннюю сеть Docker.
- **Внешний хост-Nginx:** перенаправляет трафик `stage.nurcrm.kg` (SSL Let's Encrypt, HTTP/2, WebSocket `/ws`, `/sse`) на `127.0.0.1:8088`. Все остальные проекты сервера (`market`, `nur`, `onec`, `315cargo`, `passanger_transport`, `beshtashta`) продолжают работать штатно без перезагрузок и остановок.
- **База данных:** PostgreSQL 16 с изолированными схемами и пользователями `svc_*`, применены права `USAGE`/`SELECT` для аналитики, загружены сиды стейджинга (`03_seed_stage_data.sql`).
- **AI-Ассистент:** работает вживую на домене через Google Gemini (`gemini-flash-latest`), ключ `GEMINI_API_KEY` настроен.
- **Проверка:** сквозные тесты (авторизация `owner@premium.kg`, аналитика, запросы к AI) через публичный домен `https://stage.nurcrm.kg` пройдены на 100%.

---

## 2. Недавние решения и исправления
1. **Устранение React Error #300 на фронтенде:**
   - Преобразованы анонимные inline-компоненты экранов `uslugi` и `dop-uslugi` в именованные компоненты с уникальными `key={page}` в `screens/index.tsx`.
   - В `components/shell.tsx` добавлен защитный экран загрузки `if (!ready)`, предотвращающий размонтирование хуков до инициализации стора.
   - Скрипты `dev` и `start` в `package.json` зафиксированы на `-p 3001` (порт 3000 занят оптовым фронтендом).

2. **Исправление обработчика исключений в auth-service:**
   - Исправлена опечатка `DEFAULT_EXCEPTION_HANDLER` -> `EXCEPTION_HANDLER` в `backend/services/auth/settings.py`. Исключения `CRMException` (включая 403 Forbidden) теперь отдают корректный JSON вместо падения в 500 HTML debug.

3. **Аудит и исправление модуля аналитики (`analytics-service`):**
   - Устранена ошибка PostgreSQL `InvalidParameterValue: cannot extract elements from a scalar`: вызов `jsonb_array_elements` в `repositories.py` заменён на безопасный `CROSS JOIN LATERAL` с проверкой типа массива `CASE WHEN a.services_snapshot IS NOT NULL AND jsonb_typeof(...) = 'array'`.
   - В расчет `daily_cashflow` добавлен реальный расчет оттока средств (`outflow`) из таблицы `finance.salary_payouts` вместо захардкоженного нуля.
   - Образ `deploy-analytics-service` пересобран и обновлён.

4. **Разработка AI-Ассистента по услугам (`AiAssistantWidget`):**
   - Создан компонент `components/ai-assistant.tsx`, интегрированный в `RootLayout` — доступен в правом нижнем углу на всех страницах (`fixed bottom-5 right-5 z-50`) с сохранением истории диалога при переходах.
   - Серверный обработчик `app/api/ai/chat/route.ts` и библиотека `lib/ai-service.ts`.
   - Реализована отказоустойчивая цепочка: **Gemini ➔ Claude ➔ OpenAI / Codex**.
   - При отказе всех трёх провайдеров выдаётся сообщение: *«Ведутся технические работы. Пожалуйста, обратитесь позже или свяжитесь с поддержкой.»*.
   - Ключи окружения вынесены в `.env.example`: `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`.

5. **Архитектура доменов для стейджинга:**
   - Подтверждена концепция **API Gateway**: 12 отдельных доменов под микросервисы делать **не нужно**. Все микросервисы изолированы в Docker-сети.
   - Для стейджинга требуется всего **1 домен** (например, `stage-services.nurcrm.kg`) для фронтенда, API и вебсокетов.

6. **Интеграция Jazzmin и брендинга KEZEK в админке:**
   - Установлен и настроен `django-jazzmin` (стильная тёмная тема `sidebar-dark-navy`, иконки FontAwesome для всех моделей).
   - В `settings.py` настроены `CSRF_TRUSTED_ORIGINS` (`https://stage.nurcrm.kg`), `SECURE_PROXY_SSL_HEADER` и `USE_X_FORWARDED_HOST`, что устранило ошибку 403 Forbidden при входе в админку.
   - Установлены оригинальные прозрачные логотипы: `kezek-logo-dark.png` (для тёмных фонов) и `kezek-logo-light.png` (для светлых фонов), а также квадратные иконки в шапку и сайдбар.

7. **Исправление редиректов на localhost и привязки профиля «Умар»:**
   - **Устранение редиректов на localhost:** во всех маршрутах (`proxy.ts`, `logout/route.ts`) `new URL(..., request.url)` заменён на определение актуального хоста через заголовки `X-Forwarded-Host` / `Host` и `X-Forwarded-Proto`. В Nginx (хост и шлюз) добавлены директивы `proxy_redirect ~^http://[^/]+/(.*)$ /$1;`.
   - **Устранение открытия «Умара» по умолчанию:** в `src/data/store.tsx` данные синхронизируются с реальным эндпоинтом `/api/auth/me`. Для нового/нулевого тенанта моковые сиды (`u_owner`, фиктивные визиты и смены) полностью заменяются реальными данными авторизованного владельца (`clean@nurcrm.kg`, «Владелец Нулевой»).
   - **Логотипы на фронтенде:** в `brand-panel.tsx` (тёмная панель входа) и `shell.tsx` (тёмный сайдбар) используется `kezek-logo-dark.png` и `kezek-icon-dark.png`, а на светлых экранах доступен `kezek-logo-light.png`.

---

## 3. Фокус внимания на текущем этапе
- **Стейджинг развернут и доступен:** `https://stage.nurcrm.kg/`
- **Django Admin Panel (Jazzmin + KEZEK):** `https://stage.nurcrm.kg/admin/` (логин: `admin`, пароль: `Password123!`).
- **Нулевой тестовый аккаунт (без предзаполненных данных):**
  - Email: `clean@nurcrm.kg`
  - Пароль: `Password123!`
  - Имя: `Владелец Нулевой`
  - Компания: `Чистый Сервис (Нулевой)` (UUID: `33333333-3333-3333-3333-333333333333`)
  - Данные: 0 услуг, 0 клиентов, 0 записей, 0 выручки.
- **Демо-аккаунты с заполненными данными:**
  - Owner: `owner@premium.kg` / `Password123!`
  - Support: `support@nurcrm.kg` / `Password123!`
