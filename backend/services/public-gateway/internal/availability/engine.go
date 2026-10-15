package availability

import (
	"sort"
	"time"
)

type Interval struct {
	Start time.Time `json:"start"`
	End   time.Time `json:"end"`
}

type MasterAvailability struct {
	MasterID       string   `json:"master_id"`
	MasterName     string   `json:"master_name"`
	AvailableSlots []string `json:"available_slots"` // e.g. ["09:00", "09:30", "10:00", ...]
}

type AvailabilityEngine struct {
	StepMinutes int // default 15 or 30
}

func NewAvailabilityEngine(stepMinutes int) *AvailabilityEngine {
	if stepMinutes <= 0 {
		stepMinutes = 30
	}
	return &AvailabilityEngine{StepMinutes: stepMinutes}
}

// ComputeAvailableSlots calculates free slots for a single master interval
func (e *AvailabilityEngine) ComputeAvailableSlots(
	workDate time.Time,
	workStartHour, workStartMin int,
	workEndHour, workEndMin int,
	totalDurationMin int,
	busyIntervals []Interval,
) []string {
	workStart := time.Date(workDate.Year(), workDate.Month(), workDate.Day(), workStartHour, workStartMin, 0, 0, workDate.Location())
	workEnd := time.Date(workDate.Year(), workDate.Month(), workDate.Day(), workEndHour, workEndMin, 0, 0, workDate.Location())

	duration := time.Duration(totalDurationMin) * time.Minute
	step := time.Duration(e.StepMinutes) * time.Minute

	var availableSlots []string

	for t := workStart; !t.Add(duration).After(workEnd); t = t.Add(step) {
		slotEnd := t.Add(duration)

		// Check overlap with any busy interval: [t, slotEnd) overlaps with [b.Start, b.End)
		overlaps := false
		for _, b := range busyIntervals {
			if t.Before(b.End) && b.Start.Before(slotEnd) {
				overlaps = true
				break
			}
		}

		if !overlaps {
			availableSlots = append(availableSlots, t.Format("15:04"))
		}
	}

	return availableSlots
}

// ComputeAnyMasterUnion computes unique slots available across any eligible master
func (e *AvailabilityEngine) ComputeAnyMasterUnion(mastersSlots []MasterAvailability) []string {
	slotSet := make(map[string]bool)
	for _, m := range mastersSlots {
		for _, s := range m.AvailableSlots {
			slotSet[s] = true
		}
	}

	var result []string
	for s := range slotSet {
		result = append(result, s)
	}

	sort.Strings(result)
	return result
}
