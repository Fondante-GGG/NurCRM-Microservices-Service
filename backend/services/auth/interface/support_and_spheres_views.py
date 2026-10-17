import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import connection

from libs.common.auth import verify_token, create_access_token, JWTUser, Permissions
from libs.common.exceptions import UnauthorizedError, ForbiddenError, NotFoundError, CRMException
from libs.common.response import error_response
from backend.services.auth.domain.models import Role
from backend.services.auth.infrastructure.models import (
    CompanyModel,
    EmployeeModel,
    BranchModel,
    SupportTicketModel,
    SupportLogModel,
)
from backend.services.auth.domain.industry_profiles import apply_industry_profile, INDUSTRY_PROFILES


def get_authenticated_user(request) -> JWTUser:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise UnauthorizedError("Missing or invalid Authorization header")
    token = auth_header.split(" ")[1]
    return verify_token(token)


def require_support(request) -> JWTUser:
    user = get_authenticated_user(request)
    if user.role != Role.SUPPORT:
        raise ForbiddenError("Access restricted to support team only")
    return user


def log_support_action(agent: str, company_id: uuid.UUID, action: str) -> None:
    SupportLogModel.objects.create(
        agent=agent,
        company_id=company_id,
        action=action,
    )


# -------------------------------------------------------------
# 1. Company Requisites & Industry Views (/api/main/company/)
# -------------------------------------------------------------

class MainCompanyView(APIView):
    def get(self, request):
        user = get_authenticated_user(request)
        try:
            c = CompanyModel.objects.get(id=user.company_id)
        except CompanyModel.DoesNotExist:
            raise NotFoundError("Company not found")

        phones = c.phones if isinstance(c.phones, list) else []
        return Response({
            "id": str(c.id),
            "name": c.name,
            "legal_name": c.legal_name,
            "inn": c.inn,
            "okpo": c.okpo,
            "account": c.account,
            "bik": c.bik,
            "address": c.address,
            "phones": phones,
            "industry": c.industry,
            "intake": c.intake,
        })

    def patch(self, request):
        user = get_authenticated_user(request)
        try:
            c = CompanyModel.objects.get(id=user.company_id)
        except CompanyModel.DoesNotExist:
            raise NotFoundError("Company not found")

        data = request.data or {}

        # 1. Check industry edit: Owner CANNOT change industry (403)
        if "industry" in data and data["industry"] != c.industry:
            return Response(
                {"code": "forbidden", "message": "Владелец не может менять сферу компании. Обратитесь в техподдержку."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 2. Check intake flow validation: flow allowed ONLY when industry = procedure (400)
        new_intake = data.get("intake", c.intake)
        if new_intake == "flow" and c.industry != "procedure":
            return Response(
                {"code": "invalid_intake", "message": "Режим 'поток' (flow) разрешён только при сфере 'procedure'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if "intake" in data:
            c.intake = new_intake
        if "name" in data:
            c.name = data["name"]
        if "legal_name" in data:
            c.legal_name = data["legal_name"]
        if "inn" in data:
            c.inn = data["inn"]
        if "okpo" in data:
            c.okpo = data["okpo"]
        if "account" in data:
            c.account = data["account"]
        if "bik" in data:
            c.bik = data["bik"]
        if "address" in data:
            c.address = data["address"]
        if "phones" in data:
            c.phones = data["phones"]

        c.save()

        # If performed under impersonation, write to support_log
        if user.impersonated_by:
            log_support_action(
                agent=user.impersonated_by,
                company_id=c.id,
                action=f"Обновление реквизитов и режима приёма (intake={c.intake})",
            )

        phones = c.phones if isinstance(c.phones, list) else []
        return Response({
            "id": str(c.id),
            "name": c.name,
            "legal_name": c.legal_name,
            "inn": c.inn,
            "okpo": c.okpo,
            "account": c.account,
            "bik": c.bik,
            "address": c.address,
            "phones": phones,
            "industry": c.industry,
            "intake": c.intake,
        })


class MainCompanyIndustryView(APIView):
    def post(self, request):
        user = get_authenticated_user(request)
        try:
            c = CompanyModel.objects.get(id=user.company_id)
        except CompanyModel.DoesNotExist:
            raise NotFoundError("Company not found")

        # Re-selection is conflict (409)
        if c.industry:
            return Response(
                {"code": "conflict", "message": "Сфера компании уже выбрана. Изменение возможно только через техподдержку."},
                status=status.HTTP_409_CONFLICT,
            )

        industry = request.data.get("industry")
        if industry not in ("barber", "beauty", "procedure", "massage"):
            return Response(
                {"code": "invalid_industry", "message": "Недопустимая сфера. Допустимо: barber, beauty, procedure, massage."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        c.industry = industry
        c.save()

        # Populate starter categories and positions
        apply_industry_profile(c.id, industry, reset_employees=False)

        return Response({
            "status": "success",
            "industry": c.industry,
            "message": f"Сфера '{c.industry}' успешно установлена, стартовые категории созданы.",
        })


class MainCompanyTempAccessView(APIView):
    def get(self, request):
        user = get_authenticated_user(request)
        try:
            c = CompanyModel.objects.get(id=user.company_id)
        except CompanyModel.DoesNotExist:
            raise NotFoundError("Company not found")

        until_str = c.temp_access_until.isoformat() if c.temp_access_until else None
        return Response({"until": until_str})

    def delete(self, request):
        user = get_authenticated_user(request)
        try:
            c = CompanyModel.objects.get(id=user.company_id)
        except CompanyModel.DoesNotExist:
            raise NotFoundError("Company not found")

        c.temp_access_until = None
        c.save()

        log_support_action(
            agent=f"Владелец ({user.email or user.user_id})",
            company_id=c.id,
            action="Владелец отозвал временный доступ техподдержки",
        )
        return Response({"status": "revoked", "until": None})


class MainBranchesView(APIView):
    def get(self, request):
        user = get_authenticated_user(request)
        branches = BranchModel.objects.filter(company_id=user.company_id, is_active=True).order_by("created_at")
        return Response([
            {
                "id": str(b.id),
                "name": b.name,
                "address": b.address,
                "phone": "",
                "hours": "",
                "active": b.is_active,
                "showcaseOnly": False,
            }
            for b in branches
        ])

    def post(self, request):
        return Response(
            {"code": "forbidden", "message": "Владелец филиалы создавать не может. Для подключения филиала обратитесь в техподдержку."},
            status=status.HTTP_403_FORBIDDEN,
        )



class MeView(APIView):
    def get(self, request):
        user = get_authenticated_user(request)
        try:
            emp = EmployeeModel.objects.get(id=user.user_id)
            first_name = emp.first_name
            last_name = emp.last_name
            email = emp.email
            role_display = emp.role_display
        except Exception:
            first_name = "User"
            last_name = ""
            email = user.email or ""
            role_display = user.role

        return Response({
            "id": user.user_id,
            "company_id": user.company_id,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "role": user.role,
            "role_display": role_display,
            "permissions": user.permissions,
            "impersonated_by": user.impersonated_by,
        })


# -------------------------------------------------------------
# 2. Client Support Tickets & Audit Views
# -------------------------------------------------------------

class MainSupportTicketsView(APIView):
    def get(self, request):
        user = get_authenticated_user(request)
        tickets = SupportTicketModel.objects.filter(company_id=user.company_id).order_by("-created_at")
        res = []
        for t in tickets:
            res.append({
                "id": str(t.id),
                "created_at": t.created_at.isoformat(),
                "topic": t.topic,
                "message": t.message,
                "contact": t.contact,
                "share_access": t.share_access,
                "status": t.status,
                "assignee": t.assignee,
                "reply": t.reply,
            })
        return Response(res)

    def post(self, request):
        user = get_authenticated_user(request)
        data = request.data or {}

        topic = data.get("topic", "other")
        message = data.get("message", "")
        contact = data.get("contact", "")
        share_access = bool(data.get("share_access", False))

        if not message or not contact:
            return Response(
                {"code": "validation_error", "message": "Поля message и contact обязательны"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ticket = SupportTicketModel.objects.create(
            company_id=user.company_id,
            topic=topic,
            message=message,
            contact=contact,
            share_access=share_access,
            status="new",
        )

        # If share_access is True, issue 72 hours temporary access
        if share_access:
            until = datetime.now(timezone.utc) + timedelta(hours=72)
            CompanyModel.objects.filter(id=user.company_id).update(temp_access_until=until)
            log_support_action(
                agent="Система",
                company_id=uuid.UUID(str(user.company_id)),
                action=f"Клиент запросил помощь с предоставлением доступа на 72ч (тикет #{str(ticket.id)[:8]})",
            )

        return Response({
            "id": str(ticket.id),
            "created_at": ticket.created_at.isoformat(),
            "topic": ticket.topic,
            "message": ticket.message,
            "contact": ticket.contact,
            "share_access": ticket.share_access,
            "status": ticket.status,
            "assignee": ticket.assignee,
            "reply": ticket.reply,
        }, status=status.HTTP_201_CREATED)


class MainAuditView(APIView):
    def get(self, request):
        user = get_authenticated_user(request)
        logs = SupportLogModel.objects.filter(company_id=user.company_id).order_by("-at")
        res = []
        for l in logs:
            res.append({
                "id": str(l.id),
                "at": l.at.isoformat(),
                "author": f"Техподдержка: {l.agent}" if not l.agent.startswith("Владелец") else l.agent,
                "action": l.action,
            })
        return Response(res)


# -------------------------------------------------------------
# 3. Support Staff Panel Endpoints (/api/support/...)
# -------------------------------------------------------------

class SupportCompaniesListView(APIView):
    def get(self, request):
        require_support(request)
        q = request.query_params.get("q", "").strip().lower()

        qs = CompanyModel.objects.all()
        if q:
            qs = qs.filter(name__icontains=q) | qs.filter(inn__icontains=q)

        companies = qs.order_by("-created_at")
        res = []
        for c in companies:
            branches_count = BranchModel.objects.filter(company_id=c.id, is_active=True).count()
            staff_count = EmployeeModel.objects.filter(company_id=c.id, is_active=True).count()

            # Phone
            phones = c.phones if isinstance(c.phones, list) else []
            phone = phones[0] if phones else ""

            until_str = c.temp_access_until.isoformat() if c.temp_access_until else None

            res.append({
                "id": str(c.id),
                "name": c.name,
                "phone": phone,
                "inn": c.inn,
                "industry": c.industry,
                "intake": c.intake,
                "branches_count": branches_count,
                "staff_count": staff_count,
                "plan": c.plan,
                "last_login": c.updated_at.isoformat(),
                "blocked": c.blocked,
                "temp_access_until": until_str,
            })
        return Response(res)


class SupportCompanyDetailView(APIView):
    def get(self, request, id):
        require_support(request)
        try:
            c = CompanyModel.objects.get(id=id)
        except CompanyModel.DoesNotExist:
            raise NotFoundError("Company not found")

        branches = BranchModel.objects.filter(company_id=c.id, is_active=True)
        branch_list = [{"id": str(b.id), "name": b.name, "address": b.address} for b in branches]

        phones = c.phones if isinstance(c.phones, list) else []
        until_str = c.temp_access_until.isoformat() if c.temp_access_until else None

        return Response({
            "id": str(c.id),
            "name": c.name,
            "legal_name": c.legal_name,
            "inn": c.inn,
            "okpo": c.okpo,
            "account": c.account,
            "bik": c.bik,
            "address": c.address,
            "phones": phones,
            "industry": c.industry,
            "intake": c.intake,
            "blocked": c.blocked,
            "plan": c.plan,
            "temp_access_until": until_str,
            "branches": branch_list,
        })

    def patch(self, request, id):
        agent = require_support(request)
        try:
            c = CompanyModel.objects.get(id=id)
        except CompanyModel.DoesNotExist:
            raise NotFoundError("Company not found")

        data = request.data or {}

        # 1. Intake flow check
        target_industry = data.get("industry", c.industry)
        target_intake = data.get("intake", c.intake)
        if target_intake == "flow" and target_industry != "procedure":
            return Response(
                {"code": "invalid_intake", "message": "Режим 'поток' (flow) разрешён только при сфере 'procedure'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Industry change
        industry_changed = False
        if "industry" in data and data["industry"] != c.industry:
            c.industry = data["industry"]
            industry_changed = True

        if "intake" in data:
            c.intake = target_intake
        if "blocked" in data:
            c.blocked = bool(data["blocked"])

        c.save()

        # If industry changed, recreate starter categories & positions without deleting existing records
        if industry_changed and c.industry:
            apply_industry_profile(c.id, c.industry, reset_employees=True)
            log_support_action(
                agent=agent.email or "Поддержка",
                company_id=c.id,
                action=f"Смена сферы компании на '{c.industry}' (должности сотрудников переведены в 'Специалист')",
            )

        log_support_action(
            agent=agent.email or "Поддержка",
            company_id=c.id,
            action=f"Изменение настроек компании (intake={c.intake}, blocked={c.blocked})",
        )

        return Response({"status": "updated", "industry": c.industry, "intake": c.intake, "blocked": c.blocked})


class SupportCompanyBranchesView(APIView):
    def post(self, request, id):
        agent = require_support(request)
        try:
            c = CompanyModel.objects.get(id=id)
        except CompanyModel.DoesNotExist:
            raise NotFoundError("Company not found")

        name = request.data.get("name")
        address = request.data.get("address", "")
        if not name:
            return Response({"code": "validation_error", "message": "Поле name обязательно"}, status=status.HTTP_400_BAD_REQUEST)

        branch = BranchModel.objects.create(
            company_id=c.id,
            name=name,
            address=address,
            is_active=True,
        )

        log_support_action(
            agent=agent.email or "Поддержка",
            company_id=c.id,
            action=f"Подключение филиала '{branch.name}' ({branch.address})",
        )

        return Response({
            "id": str(branch.id),
            "company_id": str(c.id),
            "name": branch.name,
            "address": branch.address,
            "is_active": branch.is_active,
        }, status=status.HTTP_201_CREATED)

    def delete(self, request, id, bid):
        agent = require_support(request)
        try:
            b = BranchModel.objects.get(id=bid, company_id=id)
        except BranchModel.DoesNotExist:
            raise NotFoundError("Branch not found")

        b.is_active = False
        b.save()

        log_support_action(
            agent=agent.email or "Поддержка",
            company_id=uuid.UUID(str(id)),
            action=f"Отключение филиала '{b.name}'",
        )

        return Response({"status": "disconnected", "id": str(bid)})


class SupportCompanyTempAccessView(APIView):
    def post(self, request, id):
        agent = require_support(request)
        try:
            c = CompanyModel.objects.get(id=id)
        except CompanyModel.DoesNotExist:
            raise NotFoundError("Company not found")

        until = datetime.now(timezone.utc) + timedelta(hours=72)
        c.temp_access_until = until
        c.save()

        log_support_action(
            agent=agent.email or "Поддержка",
            company_id=c.id,
            action=f"Выдача временного доступа на 72ч (до {until.isoformat()})",
        )

        return Response({"until": until.isoformat()})

    def delete(self, request, id):
        agent = require_support(request)
        try:
            c = CompanyModel.objects.get(id=id)
        except CompanyModel.DoesNotExist:
            raise NotFoundError("Company not found")

        c.temp_access_until = None
        c.save()

        log_support_action(
            agent=agent.email or "Поддержка",
            company_id=c.id,
            action="Отзыв временного доступа техподдержки",
        )

        return Response({"until": None, "status": "revoked"})


class SupportCompanyResetPasswordView(APIView):
    def post(self, request, id):
        agent = require_support(request)
        try:
            c = CompanyModel.objects.get(id=id)
        except CompanyModel.DoesNotExist:
            raise NotFoundError("Company not found")

        # Find owner
        owner = EmployeeModel.objects.filter(company_id=c.id, role=Role.OWNER).first()
        reset_token = str(uuid.uuid4())
        reset_link = f"https://nurcrm.kg/auth/reset-password?token={reset_token}&email={owner.email if owner else ''}"

        log_support_action(
            agent=agent.email or "Поддержка",
            company_id=c.id,
            action=f"Отправка владельцу ({owner.email if owner else ''}) ссылки на сброс пароля",
        )

        return Response({
            "status": "success",
            "message": "Ссылка на новый пароль успешно отправлена владельцу",
            "reset_link": reset_link,
        })


class SupportTicketsListView(APIView):
    def get(self, request):
        require_support(request)
        status_filter = request.query_params.get("status")

        qs = SupportTicketModel.objects.all().order_by("-created_at")
        if status_filter:
            qs = qs.filter(status=status_filter)

        res = []
        for t in qs:
            res.append({
                "id": str(t.id),
                "company_id": str(t.company_id),
                "created_at": t.created_at.isoformat(),
                "topic": t.topic,
                "message": t.message,
                "contact": t.contact,
                "share_access": t.share_access,
                "status": t.status,
                "assignee": t.assignee,
                "reply": t.reply,
            })
        return Response(res)


class SupportTicketDetailView(APIView):
    def patch(self, request, id):
        agent = require_support(request)
        try:
            ticket = SupportTicketModel.objects.get(id=id)
        except SupportTicketModel.DoesNotExist:
            raise NotFoundError("Ticket not found")

        data = request.data or {}
        new_status = data.get("status", ticket.status)
        new_assignee = data.get("assignee", ticket.assignee)
        new_reply = data.get("reply", ticket.reply)

        ticket.status = new_status
        ticket.assignee = new_assignee
        ticket.reply = new_reply
        ticket.save()

        # If status is done, and ticket had share_access = True, revoke temporary access
        if new_status == "done" and ticket.share_access:
            CompanyModel.objects.filter(id=ticket.company_id).update(temp_access_until=None)
            log_support_action(
                agent=agent.email or "Поддержка",
                company_id=ticket.company_id,
                action=f"Закрытие обращения #{str(ticket.id)[:8]} (статус 'done'), временный доступ отозван",
            )
        else:
            log_support_action(
                agent=agent.email or "Поддержка",
                company_id=ticket.company_id,
                action=f"Обновление обращения #{str(ticket.id)[:8]} (статус={ticket.status}, ответственный={ticket.assignee})",
            )

        return Response({
            "id": str(ticket.id),
            "status": ticket.status,
            "assignee": ticket.assignee,
            "reply": ticket.reply,
        })


class SupportLogView(APIView):
    def get(self, request):
        require_support(request)
        company_filter = request.query_params.get("company")

        qs = SupportLogModel.objects.all().order_by("-at")
        if company_filter:
            try:
                c_uuid = uuid.UUID(company_filter)
                qs = qs.filter(company_id=c_uuid)
            except ValueError:
                pass

        res = []
        for l in qs[:200]:
            res.append({
                "id": str(l.id),
                "at": l.at.isoformat(),
                "agent": l.agent,
                "company_id": str(l.company_id),
                "action": l.action,
            })
        return Response(res)


class SupportImpersonateView(APIView):
    def post(self, request, id):
        agent = require_support(request)
        try:
            c = CompanyModel.objects.get(id=id)
        except CompanyModel.DoesNotExist:
            raise NotFoundError("Company not found")

        # Impersonation allowed ONLY if temp_access_until is in the future
        now_dt = datetime.now(timezone.utc)
        if not c.temp_access_until or c.temp_access_until <= now_dt:
            return Response(
                {"code": "forbidden", "message": "Временный доступ не предоставлен или срок его действия истёк"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Find owner of the target company
        owner = EmployeeModel.objects.filter(company_id=c.id, role=Role.OWNER).first()
        owner_id = str(owner.id) if owner else str(uuid.uuid4())
        owner_email = owner.email if owner else f"owner@{c.slug}.nurcrm.kg"

        # Issue 1-hour access token with impersonated_by claim
        impersonation_token = create_access_token(
            user_id=owner_id,
            company_id=str(c.id),
            role=Role.OWNER,
            permissions=Permissions.ALL,
            email=owner_email,
            impersonated_by=agent.email or agent.user_id,
            expires_in_minutes=60,
        )

        log_support_action(
            agent=agent.email or "Поддержка",
            company_id=c.id,
            action=f"Вход в аккаунт компании под видом владельца (impersonated by {agent.email})",
        )

        return Response({
            "access_token": impersonation_token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "impersonated_by": agent.email or agent.user_id,
            "company_id": str(c.id),
            "company_name": c.name,
        })


class SupportImpersonateExitView(APIView):
    def post(self, request):
        user = get_authenticated_user(request)
        if user.impersonated_by:
            log_support_action(
                agent=user.impersonated_by,
                company_id=uuid.UUID(str(user.company_id)),
                action=f"Выход из аккаунта компании (impersonation exit)",
            )
        return Response({"status": "exited"})
