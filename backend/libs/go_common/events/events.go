package events

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

const (
	AuthCompanyChanged       = "auth.company.changed"
	AuthEmployeeChanged      = "auth.employee.changed"
	CatalogServiceChanged    = "catalog.service.changed"
	ClientCreated            = "client.client.created"
	ClientUpdated            = "client.client.updated"
	ScheduleAppointmentCreated = "schedule.appointment.created"
	ScheduleAppointmentUpdated = "schedule.appointment.updated"
	ScheduleAppointmentCanceled = "schedule.appointment.canceled"
	ScheduleAppointmentCompleted = "schedule.appointment.completed"
	BookingRequestCreated    = "booking.request.created"
	BookingRequestConfirmed  = "booking.request.confirmed"
	FinancePayoutCreated     = "finance.payout.created"
	FinanceShiftClosed       = "finance.shift.closed"
)

type EventEnvelope struct {
	EventID    string                 `json:"event_id"`
	Type       string                 `json:"type"`
	Version    int                    `json:"version"`
	OccurredAt string                 `json:"occurred_at"`
	CompanyID  string                 `json:"company_id"`
	TraceID    string                 `json:"trace_id"`
	ActorID    *string                `json:"actor_id,omitempty"`
	SID        *string                `json:"sid,omitempty"`
	Data       map[string]interface{} `json:"data"`
}

func NewEvent(eventType, companyID string, data map[string]interface{}) *EventEnvelope {
	return &EventEnvelope{
		EventID:    uuid.New().String(),
		Type:       eventType,
		Version:    1,
		OccurredAt: time.Now().UTC().Format(time.RFC3339),
		CompanyID:  companyID,
		TraceID:    uuid.New().String(),
		Data:       data,
	}
}

func (e *EventEnvelope) ToJSON() ([]byte, error) {
	return json.Marshal(e)
}

func FromJSON(data []byte) (*EventEnvelope, error) {
	var e EventEnvelope
	err := json.Unmarshal(data, &e)
	return &e, err
}
