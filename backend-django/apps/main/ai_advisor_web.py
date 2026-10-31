"""
«Нур Советник» в веб-админке маркета: чат с ИИ (Google Gemini) по ключам ВЛАДЕЛЬЦА, с доступом к цифрам магазина
через те же функции, что у ИИ Telegram-бота владельца (ai_analytics_functions). Только чтение: изменений товаров
веб-советник не предлагает.

Ключи: основной — тот же, что у Telegram-бота (TelegramBotSettings.ai_key, его видят касса и мобилка), плюс до 9 запасных
(CompanyAppSettings app="nur-advisor", secrets["keys"], зашифрованы). Берутся по очереди: ключ, упёршийся в лимит Google
(429) или недействительный, пропускается — до 60 с / до конца суток. Общий ключ платформы веб-советник НЕ использует.

Доступ: владелец компании + до 2 человек, которых выбрал владелец (settings["allowed_user_ids"]).
Настройки (ключи, люди, стиль ответов, дневной лимит) видит и меняет только владелец.

GET  /api/users/ai-advisor/             → {"can_use", "is_owner", "configured", "used_today", "daily_limit"}
POST /api/users/ai-advisor/ask/         {"question", "history"?: [{"role": "user"|"model", "text"}], "lang"?}
                                        → {"answer", "functions", "used_today", "daily_limit"}
GET  /api/users/ai-advisor/settings/    (владелец) → настройки, ключи замаскированы
PUT  /api/users/ai-advisor/settings/    (владелец) → то же после сохранения
POST /api/users/ai-advisor/test-key/    (владелец) {"key"} | {"id"} | {"main": true} → {"ok", "error"?}
POST /api/users/ai-advisor/ask-voice/   multipart: audio (WAV, ≤ 3 МБ ≈ 90 с), lang?, history? (JSON), speak? ("1")
                                        → {"question", "answer", "audio"? (base64 OGG/Opus), "used_today", "daily_limit"}
POST /api/users/ai-advisor/invoice/parse/  multipart file (фото/PDF ≤ 8 МБ) | {"text"} (таблица Excel/CSV) → {"rows", "unparsed"}
POST /api/users/ai-advisor/invoice/apply/  {"rows": [{product_id?, name, barcode?, qty, purchase_price, price}]} → {"done", "failed"}
                                        (владелец или допущенный с правом на склад; считается в дневной лимит)
"""
import base64
import hashlib
import json
import logging
import re
import uuid

from django.core.cache import cache
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.main.telegram_bot.crypto import decrypt_secret, encrypt_secret

log = logging.getLogger(__name__)

APP = "nur-advisor"
MAX_ALLOWED = 2
MAX_EXTRA_KEYS = 9
LENGTHS = ("short", "normal", "detailed")
TONES = ("friendly", "business")
DEFAULT_SETTINGS = {"allowed_user_ids": [], "length": "normal", "tone": "friendly", "extra": "", "daily_limit": 200,
                    "visible": {}}

# Что видят допущенные люди (не владелец). По умолчанию всё выключено.
VISIBLE_KINDS = ("salary", "money", "phones")
HIDDEN_TOOLS = {
    "salary": {"get_salary"},
    "money": {"get_pnl", "get_cashflow", "get_finance_operations", "get_reconcile"},
    "phones": set(),
}
HIDDEN_KEY_PARTS = {
    "salary": ("salary", "payroll", "wage"),
    "money": ("profit", "margin", "markup", "cost", "purchase_price", "cashflow"),
    "phones": ("phone", "whatsapp"),
}


# ----------------------------------------------------------------------------- хранение

def _company(user):
    return getattr(user, "owned_company", None) or getattr(user, "company", None)


def _is_owner(user, company):
    return company is not None and getattr(company, "owner_id", None) == user.id


def _store(company, create=False):
    from apps.users.models import CompanyAppSettings
    obj = CompanyAppSettings.objects.filter(company=company, branch__isnull=True, app=APP).first()
    if obj is None and create:
        obj = CompanyAppSettings(company=company, app=APP, settings={}, secrets={})
    return obj


def _settings(company):
    obj = _store(company)
    out = dict(DEFAULT_SETTINGS)
    if obj is not None and isinstance(obj.settings, dict):
        out.update({k: v for k, v in obj.settings.items() if k in DEFAULT_SETTINGS})
    out["allowed_user_ids"] = [str(x) for x in (out.get("allowed_user_ids") or [])][:MAX_ALLOWED]
    vis = out.get("visible") if isinstance(out.get("visible"), dict) else {}
    out["visible"] = {k: bool(vis.get(k, False)) for k in VISIBLE_KINDS}
    return out


def _hidden_kinds(user, company, s):
    """Что скрыть от этого человека: владельцу — ничего."""
    if user is None or _is_owner(user, company):
        return set()
    return {k for k in VISIBLE_KINDS if not s["visible"].get(k)}


def _scrub(data, parts):
    """Убирает из ответа функции поля, в имени которых есть скрытые слова."""
    if isinstance(data, dict):
        return {k: _scrub(v, parts) for k, v in data.items()
                if not any(p in str(k).lower() for p in parts)}
    if isinstance(data, list):
        return [_scrub(v, parts) for v in data]
    return data


def _extra_keys(company):
    """[{"id", "label", "key", "enabled"}] — расшифрованные запасные ключи."""
    obj = _store(company)
    raw = (obj.secrets or {}).get("keys") if obj is not None else None
    if not raw:
        return []
    try:
        data = json.loads(decrypt_secret(raw) or "[]")
    except Exception:
        log.warning("ai advisor: cannot decrypt extra keys for company %s", company.pk)
        return []
    return [k for k in data if isinstance(k, dict) and k.get("key")][:MAX_EXTRA_KEYS]


def _bot_settings(company):
    from apps.main.telegram_bot.models import TelegramBotSettings
    return TelegramBotSettings.objects.filter(company=company).first()


def _main_key(company):
    s = _bot_settings(company)
    return (s.ai_key or "").strip() if s is not None else ""


def _keys(company):
    """Ключи по порядку: основной, затем включённые запасные."""
    out = []
    main = _main_key(company)
    if main:
        out.append(main)
    out += [k["key"].strip() for k in _extra_keys(company) if k.get("enabled", True)]
    seen, uniq = set(), []
    for k in out:
        if k and k not in seen:
            seen.add(k)
            uniq.append(k)
    return uniq


def _mask(key):
    key = (key or "").strip()
    return (key[:4] + "…" + key[-4:]) if len(key) > 10 else ("•" * len(key))


def _can_use(user, company):
    if company is None:
        return False
    return _is_owner(user, company) or str(user.id) in _settings(company)["allowed_user_ids"]


# ----------------------------------------------------------------------------- лимиты

def _day_key(company):
    return f"ai_web_daily:{company.pk}:{timezone.localdate().isoformat()}"


def _used_today(company):
    try:
        return int(cache.get(_day_key(company)) or 0)
    except Exception:
        return 0


def _bump_today(company):
    try:
        cache.add(_day_key(company), 0, timeout=90000)
        return int(cache.incr(_day_key(company)))
    except Exception:
        return _used_today(company) + 1


def _key_blocked(key):
    try:
        return bool(cache.get("ai_web_block:" + hashlib.sha1(key.encode()).hexdigest()[:16]))
    except Exception:
        return False


def _block_key(key, seconds):
    try:
        cache.set("ai_web_block:" + hashlib.sha1(key.encode()).hexdigest()[:16], 1, timeout=seconds)
    except Exception:
        pass


# ----------------------------------------------------------------------------- ответ

def _instruction(company, s, lang):
    today = timezone.localdate()
    now = timezone.localtime()
    name = getattr(company, "name", "") or "магазина"
    length = {
        "short": "Отвечай очень коротко: 1–3 строки, только главная цифра и вывод.",
        "normal": "Отвечай по делу: главные цифры, короткий список, вывод в одну строку.",
        "detailed": "Отвечай подробно: разбивка по пунктам, сравнение с прошлым периодом, если есть данные, и 1–2 совета.",
    }[s["length"] if s["length"] in LENGTHS else "normal"]
    tone = "Тон дружелюбный, на «вы», как опытный помощник." if s["tone"] != "business" else "Тон деловой и сухой, без вводных слов."
    lang_name = {"ky": "кыргызском", "en": "английском", "tr": "турецком", "uz": "узбекском"}.get(lang, "русском")
    extra = (s.get("extra") or "").strip()[:500]
    return (
        f"Ты «Нур Советник» — ИИ-помощник владельца магазина «{name}» в системе NurCRM (веб-версия).\n"
        f"Сегодня: {today.strftime('%d.%m.%Y')}, время {now.strftime('%H:%M')}.\n\n"
        "СТРОГИЕ ПРАВИЛА:\n"
        "1. Цифры — только из результатов функций (продажи, остатки, долги, сроки годности, сотрудники, смены и др.). "
        "Выдумывать суммы, остатки и проценты запрещено. Нет данных — так и скажи.\n"
        "2. Период бери из вопроса (сегодня, вчера, неделя, прошлый месяц); если не сказан — с начала месяца.\n"
        f"3. Отвечай на {lang_name} языке; если спрашивают на другом — на нём.\n"
        "4. Формат: короткие строки, списки «• Название — 1 250 сом», жирным (**…**) только главная цифра. "
        "Таблицы и HTML не используй. Суммы — с пробелом между тысячами и словом «сом».\n"
        "5. Ты ничего не меняешь в базе: только смотришь и советуешь. Если просят изменить товар или цену — "
        "подскажи, где это сделать в разделах сайта.\n"
        f"6. {length}\n7. {tone}\n"
        + (f"8. Пожелание владельца: {extra}\n" if extra else "")
    )


def _ask(company, question, history, lang, user=None):
    from apps.main.telegram_bot.services import ai_service
    from apps.main.telegram_bot.services.ai_analytics_functions import AI_TOOL_DECLARATIONS, execute_ai_function

    s = _settings(company)
    hidden = _hidden_kinds(user, company, s)
    blocked = set().union(*(HIDDEN_TOOLS[k] for k in hidden)) if hidden else set()
    parts = tuple(p for k in hidden for p in HIDDEN_KEY_PARTS[k])
    tools = [t for t in AI_TOOL_DECLARATIONS if t.get("name") not in blocked]
    instruction = _instruction(company, s, lang)
    if hidden:
        names = {"salary": "зарплаты", "money": "прибыль, себестоимость и движение денег", "phones": "телефоны клиентов"}
        instruction += ("\nЭтому человеку владелец закрыл: " + ", ".join(names[k] for k in VISIBLE_KINDS if k in hidden)
                        + ". Если спросят об этом — вежливо скажи, что доступ закрыт владельцем.\n")

    def run_tool(name, args):
        if name in blocked:
            return {"error": "Доступ к этим данным закрыт владельцем."}
        res = execute_ai_function(company, name, args, ctx=ctx)
        return _scrub(res, parts) if parts else res
    contents = []
    for h in (history or [])[-6:]:
        role = "model" if h.get("role") == "model" else "user"
        text = str(h.get("text") or "")[:2000]
        if text:
            contents.append({"role": role, "parts": [{"text": text}]})
    contents.append({"role": "user", "parts": [{"text": question}]})
    ctx = {"settings": _bot_settings(company), "chat_id": None}

    last_error = None
    for key in _keys(company):
        if _key_blocked(key):
            continue
        try:
            text, _model, called = ai_service.generate_chat_response_with_tools(
                api_key=key,
                system_instruction=instruction,
                contents=contents,
                tools=tools,
                execute_tool_fn=run_tool,
                temperature=0.2,
                max_tokens={"short": 500, "normal": 1100, "detailed": 1800}.get(s["length"], 1100),
            )
            return text, called
        except Exception as e:  # ключ исчерпан/недействителен/сбой — пробуем следующий
            msg = str(e)
            last_error = msg
            low = msg.lower()
            if "api key not valid" in low or "api_key_invalid" in low or "permission_denied" in low:
                _block_key(key, 3600)
            elif "429" in low or "resource_exhausted" in low or "quota" in low:
                _block_key(key, 60)
            log.warning("ai advisor web: key %s failed: %s", _mask(key), msg[:200])
    raise RuntimeError(last_error or "no keys")


# ----------------------------------------------------------------------------- API

class AiAdvisorStatusAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        company = _company(request.user)
        if company is None:
            return Response({"can_use": False, "is_owner": False, "configured": False, "used_today": 0, "daily_limit": 0})
        s = _settings(company)
        return Response({
            "can_use": _can_use(request.user, company),
            "is_owner": _is_owner(request.user, company),
            "configured": bool(_keys(company)),
            "used_today": _used_today(company),
            "daily_limit": int(s["daily_limit"] or 0),
        })


class AiAdvisorAskAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        company = _company(request.user)
        if not _can_use(request.user, company):
            return Response({"code": "forbidden", "detail": "Нур Советник доступен владельцу и выбранным им людям."}, status=403)
        question = str(request.data.get("question") or "").strip()[:2000]
        if not question:
            return Response({"code": "validation_error", "detail": "Напишите вопрос."}, status=400)
        if not _keys(company):
            return Response({"code": "no_key", "detail": "Владелец ещё не добавил ключ Google Gemini."}, status=409)
        s = _settings(company)
        limit = int(s["daily_limit"] or 0)
        if limit and _used_today(company) >= limit:
            return Response({"code": "limit", "detail": f"Дневной лимит вопросов исчерпан ({limit}). Завтра снова можно.",
                             "used_today": _used_today(company), "daily_limit": limit}, status=429)
        try:
            pr_rl = f"ai_web_user:{request.user.pk}:{int(timezone.now().timestamp() // 60)}"
            cache.add(pr_rl, 0, timeout=120)
            if int(cache.incr(pr_rl)) > 12:
                return Response({"code": "too_fast", "detail": "Слишком часто. Подождите минуту."}, status=429)
        except Exception:
            pass
        lang = str(request.data.get("lang") or "ru")[:5]
        history = request.data.get("history") if isinstance(request.data.get("history"), list) else []
        try:
            answer, called = _ask(company, question, history, lang, user=request.user)
        except Exception:
            return Response({"code": "ai_unavailable",
                             "detail": "ИИ сейчас не ответил: ключи исчерпали лимит Google или недействительны. Попробуйте позже."},
                            status=503)
        used = _bump_today(company)
        return Response({"answer": answer or "Нет ответа.", "functions": called, "used_today": used, "daily_limit": limit})


def _settings_payload(company):
    s = _settings(company)
    from django.contrib.auth import get_user_model
    users = {str(u.pk): u for u in get_user_model().objects.filter(pk__in=s["allowed_user_ids"])}
    main = _main_key(company)
    return {
        "allowed_users": [{"id": uid, "name": (f"{users[uid].first_name} {users[uid].last_name}".strip() or users[uid].email)}
                          for uid in s["allowed_user_ids"] if uid in users],
        "length": s["length"], "tone": s["tone"], "extra": s["extra"], "daily_limit": int(s["daily_limit"] or 0),
        "visible": s["visible"],
        "used_today": _used_today(company),
        "main_key": {"set": bool(main), "masked": _mask(main) if main else ""},
        "keys": [{"id": k.get("id"), "label": k.get("label", ""), "masked": _mask(k["key"]), "enabled": bool(k.get("enabled", True)),
                  "blocked": _key_blocked(k["key"])} for k in _extra_keys(company)],
        "max_allowed": MAX_ALLOWED, "max_keys": MAX_EXTRA_KEYS,
    }


class AiAdvisorSettingsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _owner_company(self, request):
        company = _company(request.user)
        return company if _is_owner(request.user, company) else None

    def get(self, request):
        company = self._owner_company(request)
        if company is None:
            return Response({"code": "forbidden", "detail": "Настройки Нур Советника — только для владельца."}, status=403)
        return Response(_settings_payload(company))

    def put(self, request):
        company = self._owner_company(request)
        if company is None:
            return Response({"code": "forbidden", "detail": "Настройки Нур Советника — только для владельца."}, status=403)
        d = request.data if isinstance(request.data, dict) else {}
        errors = {}
        s = _settings(company)

        if "allowed_user_ids" in d:
            ids = [str(x) for x in (d.get("allowed_user_ids") or []) if x]
            ids = list(dict.fromkeys(ids))
            if len(ids) > MAX_ALLOWED:
                errors["allowed_user_ids"] = [f"Можно выбрать не больше {MAX_ALLOWED} человек."]
            else:
                from django.contrib.auth import get_user_model
                valid = {str(u.pk) for u in get_user_model().objects.filter(pk__in=ids, company=company)}
                ids = [i for i in ids if i in valid and i != str(request.user.pk)]
                s["allowed_user_ids"] = ids
        if isinstance(d.get("visible"), dict):
            s["visible"] = {k: bool(d["visible"].get(k, s["visible"].get(k))) for k in VISIBLE_KINDS}
        if "length" in d:
            if d["length"] in LENGTHS:
                s["length"] = d["length"]
            else:
                errors["length"] = ["Неизвестная длина ответа."]
        if "tone" in d:
            if d["tone"] in TONES:
                s["tone"] = d["tone"]
            else:
                errors["tone"] = ["Неизвестный тон."]
        if "extra" in d:
            s["extra"] = str(d.get("extra") or "").strip()[:500]
        if "daily_limit" in d:
            try:
                n = int(d.get("daily_limit"))
                if not 0 <= n <= 5000:
                    raise ValueError
                s["daily_limit"] = n
            except (TypeError, ValueError):
                errors["daily_limit"] = ["Лимит — число от 0 до 5000 (0 — без лимита)."]

        new_extra = None
        if "keys" in d:
            old = {k.get("id"): k for k in _extra_keys(company)}
            new_extra = []
            for item in (d.get("keys") or [])[:MAX_EXTRA_KEYS + 1]:
                if not isinstance(item, dict):
                    continue
                kid = str(item.get("id") or "") or uuid.uuid4().hex
                raw = str(item.get("key") or "").strip()
                key = raw or (old.get(kid) or {}).get("key", "")
                if not key:
                    continue
                if raw and (len(raw) < 20 or " " in raw):
                    errors["keys"] = ["Ключ Google Gemini выглядит неверно (обычно начинается с «AIza»)."]
                    break
                new_extra.append({"id": kid, "label": str(item.get("label") or "")[:60], "key": key, "enabled": bool(item.get("enabled", True))})
            if len(new_extra) > MAX_EXTRA_KEYS:
                errors["keys"] = [f"Не больше {MAX_EXTRA_KEYS} запасных ключей."]

        main_key = None
        if "main_key" in d and d.get("main_key") is not None:
            main_key = str(d.get("main_key") or "").strip()
            if main_key and (len(main_key) < 20 or " " in main_key):
                errors["main_key"] = ["Ключ Google Gemini выглядит неверно (обычно начинается с «AIza»)."]

        if errors:
            return Response({"code": "validation_error", "detail": next(iter(errors.values()))[0], "fields": errors}, status=400)

        obj = _store(company, create=True)
        obj.settings = {**(obj.settings or {}), **s}
        if new_extra is not None:
            secrets = dict(obj.secrets or {})
            secrets["keys"] = encrypt_secret(json.dumps(new_extra, ensure_ascii=False)) if new_extra else ""
            obj.secrets = secrets
        obj.version = (obj.version or 0) + 1
        obj.updated_by = request.user
        obj.save()

        if main_key is not None:
            from apps.main.telegram_bot.models import TelegramBotSettings
            bot, _ = TelegramBotSettings.objects.get_or_create(company=company)
            bot.ai_key = main_key
            bot.save(update_fields=["encrypted_ai_key", "updated_at"])
        return Response(_settings_payload(company))


class AiAdvisorTestKeyAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        company = _company(request.user)
        if not _is_owner(request.user, company):
            return Response({"code": "forbidden", "detail": "Только для владельца."}, status=403)
        from apps.main.telegram_bot.services import ai_service
        key = str(request.data.get("key") or "").strip()
        if not key and request.data.get("main"):
            key = _main_key(company)
        if not key and request.data.get("id"):
            key = next((k["key"] for k in _extra_keys(company) if k.get("id") == request.data.get("id")), "")
        if not key:
            return Response({"ok": False, "error": "Ключ не задан."}, status=status.HTTP_400_BAD_REQUEST)
        res = ai_service.test_ai(key)
        if not res.get("ok"):
            err = str(res.get("error") or "")
            low = err.lower()
            human = ("Ключ недействителен — проверьте, что скопировали его целиком." if "api key not valid" in low or "api_key_invalid" in low
                     else "Лимит этого ключа на сегодня исчерпан." if "429" in low or "quota" in low or "resource_exhausted" in low
                     else "Google не ответил. Попробуйте ещё раз.")
            return Response({"ok": False, "error": human})
        return Response({"ok": True})


class AiAdvisorAskVoiceAPIView(APIView):
    """Голос: запись из браузера (WAV) → распознаём ключом владельца → тот же ответ, что текстом → по желанию озвучка."""
    permission_classes = [permissions.IsAuthenticated]
    MAX_BYTES = 3 * 1024 * 1024

    def post(self, request):
        from apps.main.telegram_bot.services import ai_service
        company = _company(request.user)
        if not _can_use(request.user, company):
            return Response({"code": "forbidden", "detail": "Нур Советник доступен владельцу и выбранным им людям."}, status=403)
        audio = request.FILES.get("audio")
        if audio is None or not audio.size:
            return Response({"code": "validation_error", "detail": "Нет записи."}, status=400)
        if audio.size > self.MAX_BYTES:
            return Response({"code": "too_long", "detail": "Запись слишком длинная — до полутора минут."}, status=400)
        keys = [k for k in _keys(company) if not _key_blocked(k)]
        if not keys:
            return Response({"code": "no_key", "detail": "Владелец ещё не добавил ключ Google Gemini."}, status=409)
        s = _settings(company)
        limit = int(s["daily_limit"] or 0)
        if limit and _used_today(company) >= limit:
            return Response({"code": "limit", "detail": f"Дневной лимит вопросов исчерпан ({limit}).",
                             "used_today": _used_today(company), "daily_limit": limit}, status=429)
        raw = audio.read()
        mime = (audio.content_type or "audio/wav").split(";")[0] or "audio/wav"
        question = ""
        for key in keys[:3]:
            question = ai_service.transcribe_voice(key, raw, mime_type=mime)
            if question:
                break
        if not question:
            return Response({"code": "not_heard", "detail": "Не расслышал. Скажите ещё раз, ближе к микрофону."}, status=422)
        lang = str(request.data.get("lang") or "ru")[:5]
        try:
            history = json.loads(request.data.get("history") or "[]")
            history = history if isinstance(history, list) else []
        except (TypeError, ValueError):
            history = []
        try:
            answer, _called = _ask(company, question[:2000], history, lang, user=request.user)
        except Exception:
            return Response({"code": "ai_unavailable", "question": question,
                             "detail": "ИИ сейчас не ответил: ключи исчерпали лимит Google или недействительны."}, status=503)
        used = _bump_today(company)
        out = {"question": question, "answer": answer or "Нет ответа.", "used_today": used, "daily_limit": limit}
        if str(request.data.get("speak") or "") in ("1", "true"):
            plain = re.sub(r"<[^>]+>", "", answer or "").replace("**", "")
            for key in [k for k in _keys(company) if not _key_blocked(k)][:2]:
                try:
                    ogg = ai_service.synthesize_voice(key, plain, language="ky" if lang == "ky" else "ru")
                except Exception:
                    ogg = b""
                if ogg:
                    out["audio"] = base64.b64encode(ogg).decode("ascii")
                    break
        return Response(out)


# ----------------------------------------------------------------------------- накладная → приход

INVOICE_MAX_BYTES = 8 * 1024 * 1024
INVOICE_MAX_TEXT = 60000
INVOICE_MAX_ROWS = 500
INVOICE_MIME = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif", "application/pdf"}


def _can_stock(user, company):
    """Проводить приход: владелец или допущенный к советнику с правом на склад."""
    if _is_owner(user, company):
        return True
    return _can_use(user, company) and bool(getattr(user, "can_view_products", False))


def _min_markup(company):
    from decimal import Decimal
    s = _bot_settings(company)
    v = getattr(s, "ai_min_markup_percent", None) if s is not None else None
    return Decimal(str(v)) if v is not None else Decimal("20")


def _parse_invoice(company, parts):
    from apps.main.telegram_bot.services import ai_service
    from apps.main.telegram_bot.services.owner_actions import INVOICE_SYSTEM

    for key in _keys(company):
        if _key_blocked(key):
            continue
        data = ai_service.generate_json(key, parts, system_instruction=INVOICE_SYSTEM, max_tokens=8000)
        if isinstance(data, dict):
            return data
        _block_key(key, 60)  # ключ не ответил (лимит/сбой) — следующий
    return None


class AiAdvisorInvoiceParseAPIView(APIView):
    """POST multipart file (фото/PDF) или JSON {"text"} (таблица из Excel/CSV) → строки для проверки."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from apps.main.models import Product
        from apps.main.telegram_bot.services import owner_actions as oa

        company = _company(request.user)
        if company is None or not _can_stock(request.user, company):
            return Response({"code": "forbidden", "detail": "Нет доступа к приходу через Нур Советника."}, status=403)
        if not _keys(company):
            return Response({"code": "no_key", "detail": "Владелец ещё не добавил ключ Google Gemini."}, status=409)
        s = _settings(company)
        limit = int(s["daily_limit"] or 0)
        if limit and _used_today(company) >= limit:
            return Response({"code": "limit", "detail": f"Дневной лимит вопросов исчерпан ({limit}). Завтра снова можно."}, status=429)

        f = request.FILES.get("file")
        text = str(request.data.get("text") or "").strip() if f is None else ""
        if f is not None:
            mime = (getattr(f, "content_type", "") or "").lower()
            if mime not in INVOICE_MIME:
                return Response({"code": "format", "detail": "Нужно фото (JPG, PNG, WEBP), PDF или таблица Excel."}, status=400)
            if f.size > INVOICE_MAX_BYTES:
                return Response({"code": "too_big", "detail": "Файл больше 8 МБ."}, status=400)
            parts = [{"text": "Распознай все строки документа и верни JSON."},
                     {"inline_data": {"mime_type": mime, "data": base64.b64encode(f.read()).decode("ascii")}}]
        elif text:
            parts = [{"text": "Это таблица из Excel/CSV (колонки через «|»). Найди строки товаров и верни JSON.\n\n"
                              + text[:INVOICE_MAX_TEXT]}]
        else:
            return Response({"code": "validation_error", "detail": "Приложите фото, PDF или таблицу."}, status=400)

        data = _parse_invoice(company, parts)
        if data is None:
            return Response({"code": "ai_unavailable", "detail": "ИИ не смог прочитать документ. Попробуйте ещё раз или другое фото."},
                            status=503)
        _bump_today(company)
        parsed = {"rows": data.get("rows") if isinstance(data.get("rows"), list) else [],
                  "unparsed": [str(u) for u in (data.get("unparsed") or []) if str(u).strip()]}
        pending = oa.build_invoice_pending(company, f"web-{request.user.pk}", parsed, min_markup=_min_markup(company))
        oa.clear_pending(company.id, f"web-{request.user.pk}")
        changes = (pending.get("changes") or [])[:INVOICE_MAX_ROWS]
        products = {str(p.pk): p for p in Product.objects.filter(
            company=company, pk__in=[c["product_id"] for c in changes if c.get("product_id")])}
        rows = []
        for c in changes:
            p = products.get(str(c.get("product_id") or ""))
            rows.append({
                "product_id": str(p.pk) if p else None,
                "product_name": p.name if p else None,
                "stock_qty": str(p.quantity or 0) if p else None,
                "current_price": str(p.price or 0) if p else None,
                "name": c.get("invoice_name") or c.get("name") or "",
                "barcode": (p.barcode if p else c.get("barcode")) or "",
                "qty": c.get("qty"), "purchase_price": c.get("purchase_price"), "price": c.get("price"),
            })
        return Response({"rows": rows, "unparsed": pending.get("unparsed") or parsed["unparsed"],
                         "supplier": data.get("supplier"), "date": data.get("date"),
                         "min_markup": str(_min_markup(company))})


class AiAdvisorInvoiceApplyAPIView(APIView):
    """POST {"rows": [{product_id?, name, barcode?, qty, purchase_price, price}]} → приход/создание по каждой строке."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from decimal import Decimal, InvalidOperation
        from apps.main.telegram_bot.services import owner_actions as oa

        company = _company(request.user)
        if company is None or not _can_stock(request.user, company):
            return Response({"code": "forbidden", "detail": "Нет доступа к приходу через Нур Советника."}, status=403)
        raw = request.data.get("rows") if isinstance(request.data, dict) else None
        if not isinstance(raw, list) or not raw:
            return Response({"code": "validation_error", "detail": "Нет строк для прихода."}, status=400)
        if len(raw) > INVOICE_MAX_ROWS:
            return Response({"code": "validation_error", "detail": f"Не больше {INVOICE_MAX_ROWS} строк за раз."}, status=400)

        def num(v):
            try:
                d = Decimal(str(v).strip().replace(",", ".").replace(" ", ""))
            except (InvalidOperation, ValueError):
                return None
            return d if d.is_finite() and d >= 0 else None

        changes, errors = [], []
        for i, r in enumerate(raw):
            r = r if isinstance(r, dict) else {}
            name = str(r.get("name") or "").strip()[:255]
            qty, purchase, price = num(r.get("qty")), num(r.get("purchase_price") or 0), num(r.get("price") or 0)
            if qty is None or qty <= 0 or purchase is None or price is None:
                errors.append(f"Строка {i + 1}: проверьте количество и цены.")
                continue
            barcode = re.sub(r"\s", "", str(r.get("barcode") or "")) or None
            if r.get("product_id"):
                changes.append({"op": "stock_add", "product_id": str(r["product_id"]), "name": name, "qty": str(qty),
                                "purchase_price": str(purchase) if purchase > 0 else None,
                                "price": str(price) if price > 0 else None, "reason": "накладная (веб)"})
            elif name:
                changes.append({"op": "create_product", "name": name, "barcode": barcode, "qty": str(qty),
                                "purchase_price": str(purchase), "price": str(price), "reason": "накладная (веб)"})
            else:
                errors.append(f"Строка {i + 1}: у нового товара нет названия.")
        if errors:
            return Response({"code": "validation_error", "detail": errors[0], "errors": errors}, status=400)
        if request.data.get("create_only"):
            # приход от поставщика проводит сайт (main/suppliers/<id>/receipt/): здесь только карточки новых
            # товаров с нулевым остатком; ответ — id товара по каждой строке в том же порядке
            from apps.main.models import Product
            ids, failed = [], []
            for ch in changes:
                if ch["op"] == "stock_add":
                    ok = Product.objects.filter(pk=ch["product_id"], company=company).exists()
                    ids.append(ch["product_id"] if ok else None)
                    if not ok:
                        failed.append(f"{ch['name']}: товар не найден")
                    continue
                if ch["barcode"] and oa._product_qs(company).filter(barcode=ch["barcode"]).exists():
                    ids.append(None); failed.append(f"{ch['name']}: штрихкод {ch['barcode']} уже есть у другого товара")
                    continue
                purchase, price = oa._money(ch["purchase_price"]), oa._money(ch["price"])
                p = Product(company=company, branch=None, name=ch["name"], barcode=ch["barcode"], purchase_price=purchase,
                            markup_percent=oa._calc_markup(purchase, price), price=price, quantity=0,
                            date=timezone.now(), created_by=request.user)
                p._manual_price = True
                p.save()
                ids.append(str(p.pk))
            return Response({"ids": ids, "failed": failed})
        res = oa.execute_pending(company, f"web-{request.user.pk}", {"changes": changes, "kind": "invoice"}, user=request.user)
        import html as _html
        return Response({"done": len(res["done"]), "failed": [_html.unescape(x) for x in res["failed"]]})
