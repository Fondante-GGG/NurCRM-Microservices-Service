package availability

import (
	"testing"
	"time"
)

func TestComputeAvailableSlots(t *testing.T) {
	engine := NewAvailabilityEngine(30)

	workDate := time.Date(2026, 10, 15, 0, 0, 0, 0, time.UTC)
	workStartH, workStartM := 9, 0
	workEndH, workEndM := 12, 0 // 9:00 to 12:00 -> slots: 09:00, 09:30, 10:00, 10:30, 11:00, 11:30

	// Busy from 10:00 to 11:00
	busy := []Interval{
		{
			Start: time.Date(2026, 10, 15, 10, 0, 0, 0, time.UTC),
			End:   time.Date(2026, 10, 15, 11, 0, 0, 0, time.UTC),
		},
	}

	slots := engine.ComputeAvailableSlots(workDate, workStartH, workStartM, workEndH, workEndM, 30, busy)

	expected := []string{"09:00", "09:30", "11:00", "11:30"}

	if len(slots) != len(expected) {
		t.Fatalf("expected %d slots, got %d: %v", len(expected), len(slots), slots)
	}

	for i, s := range expected {
		if slots[i] != s {
			t.Errorf("slot at %d expected %s, got %s", i, s, slots[i])
		}
	}
}

func TestAnyMasterUnion(t *testing.T) {
	engine := NewAvailabilityEngine(30)

	m1 := MasterAvailability{
		MasterID:       "m1",
		AvailableSlots: []string{"09:00", "09:30", "10:00"},
	}
	m2 := MasterAvailability{
		MasterID:       "m2",
		AvailableSlots: []string{"10:00", "10:30", "11:00"},
	}

	union := engine.ComputeAnyMasterUnion([]MasterAvailability{m1, m2})

	expected := []string{"09:00", "09:30", "10:00", "10:30", "11:00"}

	if len(union) != len(expected) {
		t.Fatalf("expected %d unique slots, got %d: %v", len(expected), len(union), union)
	}

	for i, s := range expected {
		if union[i] != s {
			t.Errorf("at %d expected %s, got %s", i, s, union[i])
		}
	}
}
