"""
Признак версии API для касс и мобилок (единое ТЗ бэкенду 26.10.2026, Б-01).

GET /api/main/capabilities/ — любой вошедший сотрудник:
    {"api": "2026-10", "server_version": "...", "features": [...], "company_flags": {...},
     "client": "kassa/1.17.61", "client_is_new": true}
GET /api/main/client-versions/?days=7 — поддержка и суперпользователь: компания → версии клиентов.

Список features — только добавлением: касса включает новое поведение по наличию кода.
"""
import os
from datetime import timedelta

from django.db.models import Max, Sum
from django.utils import timezone
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api_compat import API_VERSION, client_label, company_flags, is_new_client

FEATURES = (
    "shift_report_v2", "cashbox_drawer_cash", "idempotency_lookup", "price_stable",
    "negative_custom_rejected", "client_documents", "bot_owner_server", "salary_payouts",
    "supplier_pay_debt", "access_codes", "changes_feed", "receipt_create_deal", "rentals_paged",
    "strict_permissions", "route_not_found", "client_header", "employee_limits", "support_constructor",
    "events_stream",  # ТЗ 29.10 Б-102: WebSocket ws/main/events/ (SSE-адрес отвечает use_websocket)
    "etag_304", "purchases",
    # ТЗ 31.10 п.16: только то, что уже работает на сервере (receipt_patch, transfer_documents,
    # stock_balance, agents — добавятся вместе с функциями)
    "share_link", "receipt_attachments", "purchase_signature", "server_addons", "product_archive", "bulk_pay_debt",
    "receipt_patch",  # ТЗ 31.10 п.21: PATCH suppliers/receipts/{id}/ (dry_run, If-Match, коды ошибок)
    # ТЗ редактор накладных 30.10 (вариант А): PATCH с Idempotency-Key, версии/откат, деньги, receipt_changed
    "receipt_edit",
    "receipt_edit_discount",  # 01.11: PATCH прихода — скидка шапки (discount / discount_percent)
    "receipt_edit_sale_price",  # 01.11: PATCH прихода — цена продажи строки (sale_price)
    # ТЗ 01.11 (витрина): Telegram-блок в публичном дизайне, ссылка на корзину c_<token>, source_detail у заказов
    "showcase_telegram", "showcase_cart_link", "showcase_order_source_detail",
    # ТЗ 01.11: чат на витрине (web_widget, согласие, удаление чата) и ИИ-помощник витрины с ключом магазина
    "showcase_chat", "showcase_assistant",
    # 03.11 front-market: CashFlow.employee + ?employee=; миниатюры image_thumb_url; pos/sales payment_method=noncash
    # и списком через запятую; suppliers/receipts ?created_by=&amount_min=&amount_max=&product_search=
    "cashflow_employee", "product_thumbs", "sales_noncash_filter", "receipts_filters",
    # 03.11 аудит S1: себе роль/права менять нельзя; роль admin и опасные права склада — только владелец/админ;
    # PATCH employees/{id}/ теперь принимает can_post_negative_stock … can_cash_negative (раньше отбрасывал)
    "employee_rights_guard",
    # S3: pos/sales и pos/returns — кассиру только свои (сервер); pos/returns/?search=
    "sales_own_only", "returns_search",
    "debt_pay_idempotency",  # S9: POST main/debts/{id}/pay/ — Idempotency-Key или idempotency_key
    "mass_incoming_purchase_price",  # G1: mass-incoming сохраняет purchase_price новой карточки всегда
    "mass_incoming_branch",  # G2: mass-incoming {branch} или ?branch= — филиал новых карточек
    "employees_list_salary",  # S2: GET users/employees/ пускает и с can_view_salary
    "cashflow_check_note_only",  # S7: cashflows/{id}/check/ {note} без checked — отметку не трогает
    # S4: construction/shifts/?date_from=&date_to= (по opened_at); pos/cart-item-deletions/ даты, user, search
    "shifts_date_filter", "cart_deletions_filters",
    # S6: CashFlow.salary_period ("YYYY-MM" или {from,to}), фильтр ?salary_period= / ?salary_period_from=&_to=
    "cashflow_salary_period",
    "products_has_promotion",  # G4: products/list/?has_promotion=true|false
    "products_piece_sale",  # G5: products/list/?piece_sale=true|false
    "products_barcodes_filter",  # G6: products/list/?barcodes=a,b,c (основной или доп. код), до 500
    "supplier_products_page_size",  # G7: suppliers/{id}/products/?page_size= (до 500)
    "rentals_branch_filter",  # S5: rentals/?branch=<uuid>|main
    "ui_dark_style",  # S8: users/ui-preferences/ dark_style (soft|classic) = theme_dark_palette
    "bundle_component_id",  # G8: packages_input[].product_id у комплекта; в ответе packages[].product_id/product_name
)


_VERSION_CACHE = []


def _detect_version():
    """ТЗ 29.10 Б-01: SERVER_VERSION (env) → /home/nur/.server_version → git short hash → "dev"."""
    for name in ("SERVER_VERSION", "NURCRM_SERVER_VERSION"):
        v = (os.getenv(name) or "").strip()
        if v:
            return v
    try:
        with open("/home/nur/.server_version", encoding="utf-8") as fh:
            v = fh.read().strip()
        if v:
            return v
    except OSError:
        pass
    try:
        import subprocess

        from django.conf import settings

        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(settings.BASE_DIR),
                             capture_output=True, text=True, timeout=3)
        v = (out.stdout or "").strip()
        if out.returncode == 0 and v:
            return v
    except Exception:
        pass
    return "dev"


def server_version():
    if not _VERSION_CACHE:
        _VERSION_CACHE.append(_detect_version())
    return _VERSION_CACHE[0]


def _company(user):
    return getattr(user, "owned_company", None) or getattr(user, "company", None)


class CapabilitiesAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        company = _company(request.user)
        return Response({
            "api": API_VERSION,
            "server_version": server_version(),
            "features": list(FEATURES),
            "company_flags": company_flags(company),
            "client": client_label(request) or None,
            "client_is_new": is_new_client(request),
        })


class IsSupportOrSuperuser(permissions.BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_superuser or getattr(u, "is_platform_admin", False)))


class ClientVersionsReportAPIView(APIView):
    permission_classes = [IsSupportOrSuperuser]

    def get(self, request):
        from apps.users.models import ClientVersionSeen

        try:
            days = max(1, min(int(request.query_params.get("days", 7)), 90))
        except ValueError:
            days = 7
        since = timezone.now() - timedelta(days=days)
        rows = (
            ClientVersionSeen.objects.filter(last_seen_at__gte=since)
            .values("company_id", "company__name", "client")
            .annotate(last_seen_at=Max("last_seen_at"), hits=Sum("hits"))
            .order_by("company__name", "client")
        )
        companies = {}
        for r in rows:
            c = companies.setdefault(str(r["company_id"]), {"company": str(r["company_id"]), "name": r["company__name"], "clients": []})
            c["clients"].append({"client": r["client"], "last_seen_at": r["last_seen_at"], "hits": r["hits"]})
        return Response({"days": days, "companies": list(companies.values())})
