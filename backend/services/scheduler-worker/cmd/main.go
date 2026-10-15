package main

import (
	"database/sql"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	_ "github.com/lib/pq"
)

const AdvisoryLockID = 987654321

func main() {
	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		dbURL = "postgres://svc_schedule:svc_schedule_secret@localhost:5432/nurcrm?sslmode=disable&search_path=schedule,public"
	}

	scheduleServiceURL := os.Getenv("SCHEDULE_SERVICE_URL")
	if scheduleServiceURL == "" {
		scheduleServiceURL = "http://localhost:8004"
	}

	intervalSeconds := 60
	if envInt := os.Getenv("INTERVAL_SECONDS"); envInt != "" {
		fmt.Sscanf(envInt, "%d", &intervalSeconds)
	}

	log.Printf("Starting NurCRM Scheduler Worker (Interval: %ds, Target: %s)...", intervalSeconds, scheduleServiceURL)

	db, err := sql.Open("postgres", dbURL)
	if err != nil {
		log.Printf("Warning: Database connection failed: %v. Running in standalone HTTP mode.", err)
	} else {
		defer db.Close()
	}

	ticker := time.NewTicker(time.Duration(intervalSeconds) * time.Second)
	defer ticker.Stop()

	stopChan := make(chan os.Signal, 1)
	signal.Notify(stopChan, os.Interrupt, syscall.SIGTERM)

	// Run once immediately on start
	runTick(db, scheduleServiceURL)

	for {
		select {
		case <-ticker.C:
			runTick(db, scheduleServiceURL)
		case <-stopChan:
			log.Println("Stopping Scheduler Worker gracefully...")
			return
		}
	}
}

func runTick(db *sql.DB, scheduleURL string) {
	log.Printf("[%s] Executing appointment auto-complete check...", time.Now().UTC().Format(time.RFC3339))

	var acquiredLock bool = true

	// If DB is reachable, attempt advisory lock
	if db != nil && db.Ping() == nil {
		row := db.QueryRow("SELECT pg_try_advisory_lock($1)", AdvisoryLockID)
		if err := row.Scan(&acquiredLock); err != nil {
			log.Printf("Error trying advisory lock: %v", err)
			acquiredLock = false
		}
	}

	if !acquiredLock {
		log.Println("Advisory lock held by another worker instance. Skipping tick.")
		return
	}

	defer func() {
		if db != nil && db.Ping() == nil {
			db.Exec("SELECT pg_advisory_unlock($1)", AdvisoryLockID)
		}
	}()

	// Call schedule-service internal endpoint: POST /internal/v1/appointments/auto-complete/
	endpoint := fmt.Sprintf("%s/internal/v1/appointments/auto-complete/", scheduleURL)
	req, err := http.NewRequest(http.MethodPost, endpoint, nil)
	if err != nil {
		log.Printf("Failed to create request: %v", err)
		return
	}

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("Failed to call auto-complete endpoint: %v", err)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusOK {
		log.Printf("Auto-complete tick executed successfully (status: %d)", resp.StatusCode)
	} else {
		log.Printf("Auto-complete endpoint returned unexpected status: %d", resp.StatusCode)
	}
}
