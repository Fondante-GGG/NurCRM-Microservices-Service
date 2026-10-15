from fastapi import FastAPI, Depends, Header, HTTPException, Query
from typing import Optional
import uuid
from datetime import date

from libs.common.auth import verify_token, JWTUser
from libs.common.exceptions import UnauthorizedError, ForbiddenError
from backend.services.analytics.infrastructure.repositories import AnalyticsRepository

app = FastAPI(title="NurCRM Analytics Service", version="1.0.0")


def get_current_user(authorization: Optional[str] = Header(None)) -> JWTUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Missing token"})
    token = authorization.split(" ")[1]
    try:
        user = verify_token(token)
        return user
    except Exception as e:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": str(e)})


@app.get("/api/v1/analytics/dashboard/")
@app.get("/api/barbershop/analytics/dashboard/")
def get_dashboard(
    period: str = Query("month", regex="^(day|month|last_month|range)$"),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    current_user: JWTUser = Depends(get_current_user),
):
    repo = AnalyticsRepository()
    dashboard = repo.get_dashboard(
        company_id=uuid.UUID(current_user.company_id),
        period=period,
        date_from=date_from,
        date_to=date_to,
    )
    return {
        "period": dashboard.period,
        "financial": {
            "revenue_total": str(dashboard.revenue_total),
            "cash_in": str(dashboard.cash_in),
            "cash_out": str(dashboard.cash_out),
            "avg_ticket": str(dashboard.avg_ticket),
        },
        "appointments": {
            "total": dashboard.total_appointments,
            "completed": dashboard.completed_count,
            "canceled": dashboard.canceled_count,
            "no_show": dashboard.no_show_count,
            "conversion_rate": dashboard.conversion_rate,
        },
        "rankings": {
            "top_masters": [
                {
                    "master_id": m.master_id,
                    "master_name": m.master_name,
                    "appointments_count": m.appointments_count,
                    "revenue": str(m.revenue),
                }
                for m in dashboard.top_masters
            ],
            "top_services": [
                {
                    "service_id": s.service_id,
                    "service_name": s.service_name,
                    "orders_count": s.orders_count,
                    "revenue": str(s.revenue),
                }
                for s in dashboard.top_services
            ],
            "top_clients": [
                {
                    "client_id": c.client_id,
                    "client_name": c.client_name,
                    "visits_count": c.visits_count,
                    "total_spent": str(c.total_spent),
                }
                for c in dashboard.top_clients
            ],
        },
        "charts": {
            "weekday_distribution": dashboard.weekday_distribution,
            "daily_cashflow": dashboard.daily_cashflow,
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
