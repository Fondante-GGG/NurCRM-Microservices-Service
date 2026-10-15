import pytest
import uuid
from decimal import Decimal
from datetime import datetime, date, time, timedelta, timezone

from libs.common.domain import Money, Phone, TimeSlot
from libs.common.exceptions import (
    ValidationError,
    SlotBusyError,
    VersionConflictError,
    AlreadyProcessedError,
    ShiftAlreadyOpenError,
    ClientExistsError,
)
from libs.common.auth import create_access_token, verify_token, KeyManager
from libs.common.outbox import InMemoryOutboxRepository, InMemoryInboxRepository

# Auth domain
from backend.services.auth.domain.models import Company, Employee, Role

# Catalog domain
from backend.services.catalog.domain.models import Service, ServiceCategory, SalaryRate

# Client domain
from backend.services.client.domain.models import Client, ClientDocument

# Schedule domain & use cases
from backend.services.schedule.domain.models import Appointment, ServiceSnapshot, AppointmentStatus
from backend.services.schedule.application.use_cases import CreateAppointmentUseCase
from backend.services.schedule.application.dto import CreateAppointmentDTO

# Booking domain & saga
from backend.services.booking.domain.models import BookingRequest, BookingStatus
from backend.services.booking.application.use_cases import ConfirmBookingSagaUseCase

# Finance domain
from backend.services.finance.domain.models import Accrual, SalaryPayout, CashShift


class TestValueObjectsAndDomainBases:
    def test_money_arithmetic(self):
        m1 = Money(Decimal("100.50"))
        m2 = Money(Decimal("50.25"))
        m3 = m1 + m2
        assert m3.amount == Decimal("150.75")
        assert m3.currency == "KGS"

        m4 = m1 * 2
        assert m4.amount == Decimal("201.00")

    def test_phone_formatting_and_validation(self):
        p1 = Phone("0555123456")
        assert p1.value == "+996555123456"

        p2 = Phone("+996 700 11 22 33")
        assert p2.value == "+996700112233"

        with pytest.raises(ValueError):
            Phone("")

    def test_timeslot_overlap(self):
        now = datetime.now(timezone.utc)
        slot1 = TimeSlot(now, now + timedelta(minutes=60))
        slot2 = TimeSlot(now + timedelta(minutes=30), now + timedelta(minutes=90))
        slot3 = TimeSlot(now + timedelta(minutes=60), now + timedelta(minutes=120))

        assert slot1.overlaps_with(slot2) is True
        assert slot1.overlaps_with(slot3) is False  # boundary touch is not an overlap


class TestAuthAndJWT:
    def test_jwt_issuance_and_verification(self):
        user_id = str(uuid.uuid4())
        company_id = str(uuid.uuid4())
        token = create_access_token(
            user_id=user_id,
            company_id=company_id,
            role="owner",
            permissions=["can_view_salary", "can_view_barber_records"],
        )
        assert token is not None

        user = verify_token(token)
        assert user.user_id == user_id
        assert user.company_id == company_id
        assert user.role == "owner"
        assert user.has_perm("can_view_salary") is True

    def test_employee_password_hashing(self):
        raw = "secret123"
        hashed = Employee.hash_password(raw)
        emp = Employee(id=uuid.uuid4(), company_id=uuid.uuid4(), password_hash=hashed)
        assert emp.check_password(raw) is True
        assert emp.check_password("wrong") is False


class TestScheduleAndConflictResolution:
    def test_appointment_duration_and_price_calculation(self):
        cid = uuid.uuid4()
        mid = uuid.uuid4()
        now = datetime.now(timezone.utc)

        services = [
            ServiceSnapshot(uuid.uuid4(), "Стрижка", Money(Decimal("800.00")), 30),
            ServiceSnapshot(uuid.uuid4(), "Борода", Money(Decimal("400.00")), 30),
        ]

        appt = Appointment.create(
            company_id=cid,
            client_name="Асан",
            barber_id=mid,
            services=services,
            start_at=now,
            discount=Money(Decimal("100.00")),
        )

        # end_at = start_at + 60 minutes
        assert appt.end_at == now + timedelta(minutes=60)
        # Price = 800 + 400 - 100 = 1100
        assert appt.price.amount == Decimal("1100.00")
        assert appt.status == AppointmentStatus.BOOKED

    def test_appointment_terminal_status_transitions(self):
        appt = Appointment(
            id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            status=AppointmentStatus.COMPLETED,
        )
        # Completed is terminal, cannot transition back to booked or confirmed
        with pytest.raises(Exception):
            appt.transition_status(AppointmentStatus.BOOKED)


class TestBookingConfirmationSaga:
    class MockScheduleRepo:
        def __init__(self, conflict=False):
            self.conflict = conflict
            self.saved = []

        def get_overlapping(self, **kwargs):
            if self.conflict:
                return [Appointment(id=uuid.uuid4(), company_id=uuid.uuid4())]
            return []

        def save(self, appt):
            self.saved.append(appt)

    class MockClientService:
        def find_or_create_client(self, company_id, full_name, phone):
            return {"id": str(uuid.uuid4()), "full_name": full_name, "phone": phone}

    class MockScheduleService:
        def __init__(self, slot_busy=False):
            self.slot_busy = slot_busy

        def create_appointment(self, **kwargs):
            if self.slot_busy:
                raise SlotBusyError("Slot is busy")
            return {"id": str(uuid.uuid4()), "status": "confirmed"}

    class MockBookingUoW:
        def __init__(self, booking):
            self.booking = booking
            self.events = []
            self.bookings = self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get_by_id(self, company_id, booking_id):
            return self.booking

        def save(self, b):
            self.booking = b

        def record_outbox(self, event):
            self.events.append(event)

        def commit(self):
            pass

    def test_saga_success(self):
        cid = uuid.uuid4()
        mid = uuid.uuid4()
        booking = BookingRequest(
            id=uuid.uuid4(),
            company_id=cid,
            client_name="Тимур",
            client_phone=Phone("+996555112233"),
            master_id=mid,
            date=date.today(),
            time_start=time(10, 0),
            time_end=time(10, 30),
            status=BookingStatus.NEW,
        )

        uow = self.MockBookingUoW(booking)
        client_svc = self.MockClientService()
        schedule_svc = self.MockScheduleService(slot_busy=False)

        saga = ConfirmBookingSagaUseCase(uow, client_svc, schedule_svc)
        res = saga.execute(cid, booking.id, actor_name="admin@nurcrm.kg")

        assert res.status == BookingStatus.CONFIRMED
        assert res.appointment_id is not None
        assert len(uow.events) == 1
        assert uow.events[0].type == "booking.request.confirmed"

    def test_saga_slot_busy_keeps_booking_new(self):
        cid = uuid.uuid4()
        mid = uuid.uuid4()
        booking = BookingRequest(
            id=uuid.uuid4(),
            company_id=cid,
            client_name="Тимур",
            client_phone=Phone("+996555112233"),
            master_id=mid,
            date=date.today(),
            time_start=time(10, 0),
            time_end=time(10, 30),
            status=BookingStatus.NEW,
        )

        uow = self.MockBookingUoW(booking)
        client_svc = self.MockClientService()
        schedule_svc = self.MockScheduleService(slot_busy=True)

        saga = ConfirmBookingSagaUseCase(uow, client_svc, schedule_svc)
        with pytest.raises(SlotBusyError):
            saga.execute(cid, booking.id)

        # Booking status remains 'new'
        assert booking.status == BookingStatus.NEW
        assert booking.appointment_id is None


class TestFinanceAndAccrualLogic:
    def test_accrual_calculation(self):
        cid = uuid.uuid4()
        appt_id = uuid.uuid4()
        mid = uuid.uuid4()

        # Service price: 1500 KGS, rate: 40% -> Accrual = 600 KGS
        accrual = Accrual.calculate(
            company_id=cid,
            appointment_id=appt_id,
            master_id=mid,
            service_price=Money(Decimal("1500.00")),
            percent=Decimal("40.00"),
        )

        assert accrual.amount.amount == Decimal("600.00")
        assert accrual.percent == Decimal("40.00")

    def test_cash_shift_close(self):
        shift = CashShift(
            id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            opening_cash=Money(Decimal("5000.00")),
            status="open",
        )
        assert shift.version == 1

        shift.close(
            closing_cash=Money(Decimal("25000.00")),
            sales_total=Money(Decimal("20000.00")),
            sales_count=15,
        )

        assert shift.status == "closed"
        assert shift.closing_cash.amount == Decimal("25000.00")
        assert shift.version == 2
