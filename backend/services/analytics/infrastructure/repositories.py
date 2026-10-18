import os
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal
from datetime import datetime, date, timedelta, time, timezone
from typing import Optional, Dict, Any, List

from backend.services.analytics.domain.models import (
    AnalyticsDashboard,
    MasterRankingItem,
    ServiceRankingItem,
    ClientRankingItem,
)


class AnalyticsRepository:
    """PostgreSQL analytical query repository computing real-time metrics across microservice schemas."""

    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn or os.getenv(
            "DATABASE_URL",
            f"postgresql://{os.getenv('DB_USER', 'svc_analytics')}:{os.getenv('DB_PASSWORD', 'svc_analytics_secret')}@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', 'nurcrm')}"
        )

    def _get_conn(self):
        return psycopg2.connect(self.dsn)

    def get_dashboard(
        self,
        company_id: uuid.UUID,
        period: str = "month",
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> AnalyticsDashboard:
        today = date.today()
        if period == "day":
            d_from = today
            d_to = today
        elif period == "last_month":
            first_day_current = today.replace(day=1)
            last_day_prev = first_day_current - timedelta(days=1)
            d_from = last_day_prev.replace(day=1)
            d_to = last_day_prev
        elif period == "range" and date_from and date_to:
            d_from = date_from
            d_to = date_to
        else:  # default 'month'
            d_from = today.replace(day=1)
            d_to = today

        dt_from = datetime.combine(d_from, time.min).replace(tzinfo=timezone.utc)
        dt_to = datetime.combine(d_to, time.max).replace(tzinfo=timezone.utc)
        cid_str = str(company_id)

        revenue_total = Decimal("0.00")
        total_appts = 0
        completed_count = 0
        canceled_count = 0
        no_show_count = 0
        cash_in = Decimal("0.00")
        cash_out = Decimal("0.00")

        top_masters: List[MasterRankingItem] = []
        top_services: List[ServiceRankingItem] = []
        top_clients: List[ClientRankingItem] = []
        weekday_map = {
            1: "Понедельник",
            2: "Вторник",
            3: "Среда",
            4: "Четверг",
            5: "Пятница",
            6: "Суббота",
            7: "Воскресенье",
        }
        weekday_distribution = {name: 0 for name in weekday_map.values()}
        daily_cashflow: List[Dict[str, Any]] = []

        with self._get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 1. Appointments counts and revenue
                cur.execute(
                    """
                    SELECT status, count(*) as cnt, COALESCE(sum(price), 0) as total_price
                    FROM schedule.appointments
                    WHERE company_id = %s AND start_at >= %s AND start_at <= %s
                    GROUP BY status;
                    """,
                    (cid_str, dt_from, dt_to),
                )
                for row in cur.fetchall():
                    c = int(row["cnt"])
                    total_appts += c
                    st = row["status"]
                    if st in ("completed", "paid"):
                        completed_count += c
                        revenue_total += Decimal(str(row["total_price"]))
                    elif st == "canceled":
                        canceled_count += c
                    elif st == "no_show":
                        no_show_count += c

                # 2. Finance cash shifts and payouts
                cur.execute(
                    """
                    SELECT COALESCE(sum(sales_total), 0) as c_in
                    FROM finance.cash_shifts
                    WHERE company_id = %s AND opened_at >= %s AND opened_at <= %s;
                    """,
                    (cid_str, dt_from, dt_to),
                )
                cf_row = cur.fetchone()
                if cf_row:
                    cash_in = Decimal(str(cf_row["c_in"]))

                cur.execute(
                    """
                    SELECT COALESCE(sum(amount), 0) as c_out
                    FROM finance.salary_payouts
                    WHERE company_id = %s AND created_at >= %s AND created_at <= %s;
                    """,
                    (cid_str, dt_from, dt_to),
                )
                p_row = cur.fetchone()
                if p_row:
                    cash_out = Decimal(str(p_row["c_out"]))

                if cash_in == Decimal("0.00") and revenue_total > Decimal("0.00"):
                    cash_in = revenue_total

                # 3. Top Masters
                cur.execute(
                    """
                    SELECT a.barber_id,
                           COALESCE(e.first_name || ' ' || e.last_name, 'Мастер') as m_name,
                           count(*) as cnt,
                           COALESCE(sum(a.price), 0) as rev
                    FROM schedule.appointments a
                    LEFT JOIN auth.employees e ON e.id = a.barber_id
                    WHERE a.company_id = %s AND a.barber_id IS NOT NULL AND a.status IN ('completed', 'paid')
                      AND a.start_at >= %s AND a.start_at <= %s
                    GROUP BY a.barber_id, e.first_name, e.last_name
                    ORDER BY rev DESC
                    LIMIT 5;
                    """,
                    (cid_str, dt_from, dt_to),
                )
                for r in cur.fetchall():
                    top_masters.append(MasterRankingItem(
                        master_id=str(r["barber_id"]),
                        master_name=r["m_name"],
                        appointments_count=int(r["cnt"]),
                        revenue=Decimal(str(r["rev"])),
                    ))

                # 4. Top Services
                cur.execute(
                    """
                    SELECT s->>'service_id' as sid,
                           s->>'name' as sname,
                           count(*) as cnt,
                           COALESCE(sum((s->>'price')::numeric), 0) as rev
                    FROM schedule.appointments a
                    CROSS JOIN LATERAL jsonb_array_elements(
                        CASE 
                            WHEN a.services_snapshot IS NOT NULL 
                             AND jsonb_typeof(a.services_snapshot::jsonb) = 'array' 
                            THEN a.services_snapshot::jsonb 
                            ELSE '[]'::jsonb 
                        END
                    ) as s
                    WHERE a.company_id = %s AND a.status IN ('completed', 'paid')
                      AND a.start_at >= %s AND a.start_at <= %s
                    GROUP BY sid, sname
                    ORDER BY rev DESC
                    LIMIT 5;
                    """,
                    (cid_str, dt_from, dt_to),
                )
                for r in cur.fetchall():
                    if r["sid"]:
                        top_services.append(ServiceRankingItem(
                            service_id=str(r["sid"]),
                            service_name=r["sname"] or "Услуга",
                            orders_count=int(r["cnt"]),
                            revenue=Decimal(str(r["rev"])),
                        ))

                # 5. Top Clients
                cur.execute(
                    """
                    SELECT COALESCE(a.client_id::text, '') as cid,
                           a.client_name,
                           count(*) as visits,
                           COALESCE(sum(a.price), 0) as spent
                    FROM schedule.appointments a
                    WHERE a.company_id = %s AND a.status IN ('completed', 'paid')
                      AND a.start_at >= %s AND a.start_at <= %s
                    GROUP BY a.client_id, a.client_name
                    ORDER BY spent DESC
                    LIMIT 5;
                    """,
                    (cid_str, dt_from, dt_to),
                )
                for r in cur.fetchall():
                    top_clients.append(ClientRankingItem(
                        client_id=r["cid"],
                        client_name=r["client_name"],
                        visits_count=int(r["visits"]),
                        total_spent=Decimal(str(r["spent"])),
                    ))

                # 6. Weekday distribution
                cur.execute(
                    """
                    SELECT EXTRACT(ISODOW FROM start_at)::int as dow, count(*) as cnt
                    FROM schedule.appointments
                    WHERE company_id = %s AND start_at >= %s AND start_at <= %s
                    GROUP BY dow;
                    """,
                    (cid_str, dt_from, dt_to),
                )
                for r in cur.fetchall():
                    day_name = weekday_map.get(int(r["dow"]))
                    if day_name:
                        weekday_distribution[day_name] = int(r["cnt"])

                # 7. Daily cashflow
                flow_by_date = {}
                cur.execute(
                    """
                    SELECT DATE(opened_at) as dt,
                           COALESCE(sum(sales_total), 0) as inf
                    FROM finance.cash_shifts
                    WHERE company_id = %s AND opened_at >= NOW() - INTERVAL '7 days'
                    GROUP BY dt
                    ORDER BY dt ASC;
                    """,
                    (cid_str,),
                )
                for r in cur.fetchall():
                    d_str = str(r["dt"])
                    flow_by_date[d_str] = {"date": d_str, "inflow": str(r["inf"]), "outflow": "0.00"}

                cur.execute(
                    """
                    SELECT DATE(created_at) as dt,
                           COALESCE(sum(amount), 0) as outf
                    FROM finance.salary_payouts
                    WHERE company_id = %s AND created_at >= NOW() - INTERVAL '7 days'
                    GROUP BY dt
                    ORDER BY dt ASC;
                    """,
                    (cid_str,),
                )
                for r in cur.fetchall():
                    d_str = str(r["dt"])
                    if d_str in flow_by_date:
                        flow_by_date[d_str]["outflow"] = str(r["outf"])
                    else:
                        flow_by_date[d_str] = {"date": d_str, "inflow": "0.00", "outflow": str(r["outf"])}

                daily_cashflow = sorted(flow_by_date.values(), key=lambda x: x["date"])

        avg_ticket = (revenue_total / Decimal(completed_count)).quantize(Decimal("0.01")) if completed_count > 0 else Decimal("0.00")
        conversion = round((completed_count / total_appts) * 100, 2) if total_appts > 0 else 0.0

        return AnalyticsDashboard(
            period=period,
            revenue_total=revenue_total,
            cash_in=cash_in,
            cash_out=cash_out,
            avg_ticket=avg_ticket,
            total_appointments=total_appts,
            completed_count=completed_count,
            canceled_count=canceled_count,
            no_show_count=no_show_count,
            conversion_rate=conversion,
            top_masters=top_masters,
            top_services=top_services,
            top_clients=top_clients,
            weekday_distribution=weekday_distribution,
            daily_cashflow=daily_cashflow,
        )
