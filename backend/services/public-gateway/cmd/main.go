package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/nurcrm/backend/libs/go_common/redis"
	"github.com/nurcrm/backend/services/public-gateway/internal/availability"
)

type GatewayConfig struct {
	Port              string
	RedisAddr         string
	AuthServiceURL    string
	CatalogServiceURL string
	ScheduleServiceURL string
	BookingServiceURL string
}

func getEnv(key, defaultVal string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return defaultVal
}

type PublicGateway struct {
	cfg    GatewayConfig
	redis  *redis.Client
	engine *availability.AvailabilityEngine
}

func main() {
	cfg := GatewayConfig{
		Port:               getEnv("PORT", "8010"),
		RedisAddr:          getEnv("REDIS_ADDR", "localhost:6379"),
		AuthServiceURL:     getEnv("AUTH_SERVICE_URL", "http://localhost:8001"),
		CatalogServiceURL:  getEnv("CATALOG_SERVICE_URL", "http://localhost:8002"),
		ScheduleServiceURL: getEnv("SCHEDULE_SERVICE_URL", "http://localhost:8004"),
		BookingServiceURL:  getEnv("BOOKING_SERVICE_URL", "http://localhost:8005"),
	}

	rClient := redis.NewClient(cfg.RedisAddr, "", 0)
	gw := &PublicGateway{
		cfg:    cfg,
		redis:  rClient,
		engine: availability.NewAvailabilityEngine(30),
	}

	mux := http.NewServeMux()

	// Public widget endpoints
	mux.HandleFunc("/api/barbershop/public/", gw.handlePublicRoutes)
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"ok"}`))
	})

	// Wrap with CORS & Logging
	handler := withCORS(mux)

	log.Printf("Starting Public Gateway on port %s...", cfg.Port)
	if err := http.ListenAndServe(":"+cfg.Port, handler); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}

func withCORS(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusOK)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func (gw *PublicGateway) handlePublicRoutes(w http.ResponseWriter, r *http.Request) {
	// Path format: /api/barbershop/public/{slug}/{resource}/
	path := strings.TrimPrefix(r.URL.Path, "/api/barbershop/public/")
	parts := strings.Split(strings.Trim(path, "/"), "/")
	if len(parts) < 2 {
		http.Error(w, `{"code":"not_found","message":"Invalid endpoint path"}`, http.StatusNotFound)
		return
	}

	slug := parts[0]
	resource := parts[1]

	w.Header().Set("Content-Type", "application/json")

	switch resource {
	case "service-categories":
		gw.handleServiceCategories(w, r, slug)
	case "services":
		gw.handleServices(w, r, slug)
	case "masters":
		if len(parts) >= 3 && parts[2] == "availability" {
			gw.handleAvailability(w, r, slug)
		} else {
			gw.handleMasters(w, r, slug)
		}
	case "bookings":
		if r.Method == http.MethodPost {
			gw.handleCreateBooking(w, r, slug)
		} else {
			http.Error(w, `{"code":"method_not_allowed"}`, http.StatusMethodNotAllowed)
		}
	default:
		http.Error(w, `{"code":"not_found"}`, http.StatusNotFound)
	}
}

func (gw *PublicGateway) handleServiceCategories(w http.ResponseWriter, r *http.Request, slug string) {
	// Sample mock / proxy categories
	res := []map[string]interface{}{
		{"id": "11111111-1111-1111-1111-111111111111", "name": "Волосы", "is_active": true},
		{"id": "22222222-2222-2222-2222-222222222222", "name": "Борода и бритье", "is_active": true},
		{"id": "33333333-3333-3333-3333-333333333333", "name": "SPA и Массаж", "is_active": true},
	}
	json.NewEncoder(w).Encode(res)
}

func (gw *PublicGateway) handleServices(w http.ResponseWriter, r *http.Request, slug string) {
	// Try Redis cache
	ctx, cancel := context.WithTimeout(context.Background(), 200*time.Millisecond)
	defer cancel()

	cached, err := gw.redis.GetPublicServices(ctx, slug)
	if err == nil && len(cached) > 0 {
		w.Write(cached)
		return
	}

	// Fallback response
	services := []map[string]interface{}{
		{
			"id":           "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
			"name":         "Стрижка классическая",
			"price":        "800.00",
			"time_minutes": 30,
			"is_active":    true,
		},
		{
			"id":           "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
			"name":         "Моделирование бороды",
			"price":        "600.00",
			"time_minutes": 30,
			"is_active":    true,
		},
		{
			"id":           "cccccccc-cccc-cccc-cccc-cccccccccccc",
			"name":         "Комплекс (Стрижка + Борода)",
			"price":        "1200.00",
			"time_minutes": 60,
			"is_active":    true,
		},
	}
	data, _ := json.Marshal(services)
	gw.redis.SetPublicServices(ctx, slug, data, 300*time.Second)
	w.Write(data)
}

func (gw *PublicGateway) handleMasters(w http.ResponseWriter, r *http.Request, slug string) {
	masters := []map[string]interface{}{
		{
			"id":           "m1111111-1111-1111-1111-111111111111",
			"first_name":   "Айбек",
			"last_name":    "Касымов",
			"role_display": "Топ-барбер",
			"avatar":       nil,
		},
		{
			"id":           "m2222222-2222-2222-2222-222222222222",
			"first_name":   "Адилет",
			"last_name":    "Оморов",
			"role_display": "Мастер",
			"avatar":       nil,
		},
	}
	json.NewEncoder(w).Encode(masters)
}

func (gw *PublicGateway) handleAvailability(w http.ResponseWriter, r *http.Request, slug string) {
	dateStr := r.URL.Query().Get("date")
	if dateStr == "" {
		dateStr = time.Now().Format("2006-01-02")
	}

	targetDate, err := time.Parse("2006-01-02", dateStr)
	if err != nil {
		http.Error(w, `{"code":"validation_error","message":"Invalid date format YYYY-MM-DD"}`, http.StatusBadRequest)
		return
	}

	durationMin := 30
	if durStr := r.URL.Query().Get("duration_min"); durStr != "" {
		if d, err := strconv.Atoi(durStr); err == nil && d > 0 {
			durationMin = d
		}
	}

	masterID := r.URL.Query().Get("master_id")

	// Work interval: 09:00 - 21:00
	workStartH, workStartM := 9, 0
	workEndH, workEndM := 21, 0

	// Simulated busy intervals for testing
	var busyIntervals []availability.Interval
	if masterID != "" {
		// Mock a busy slot 13:00 - 14:00
		bStart := time.Date(targetDate.Year(), targetDate.Month(), targetDate.Day(), 13, 0, 0, 0, targetDate.Location())
		bEnd := time.Date(targetDate.Year(), targetDate.Month(), targetDate.Day(), 14, 0, 0, 0, targetDate.Location())
		busyIntervals = append(busyIntervals, availability.Interval{Start: bStart, End: bEnd})
	}

	slots := gw.engine.ComputeAvailableSlots(targetDate, workStartH, workStartM, workEndH, workEndM, durationMin, busyIntervals)

	response := map[string]interface{}{
		"date":            dateStr,
		"duration_min":    durationMin,
		"master_id":       masterID,
		"available_slots": slots,
	}

	json.NewEncoder(w).Encode(response)
}

func (gw *PublicGateway) handleCreateBooking(w http.ResponseWriter, r *http.Request, slug string) {
	bodyBytes, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, `{"code":"bad_request"}`, http.StatusBadRequest)
		return
	}

	var reqData map[string]interface{}
	if err := json.Unmarshal(bodyBytes, &reqData); err != nil {
		http.Error(w, `{"code":"validation_error","message":"Invalid JSON body"}`, http.StatusBadRequest)
		return
	}

	// Get company info by slug from auth-service
	companyResp, err := http.Get(fmt.Sprintf("%s/internal/v1/companies/slug/%s/", gw.cfg.AuthServiceURL, slug))
	var companyID string
	if err == nil && companyResp.StatusCode == http.StatusOK {
		var compData map[string]interface{}
		json.NewDecoder(companyResp.Body).Decode(&compData)
		companyID, _ = compData["id"].(string)
		companyResp.Body.Close()
	}

	if companyID == "" {
		// Fallback sample UUID if auth service is offline
		companyID = "00000000-0000-0000-0000-000000000001"
	}

	reqData["company_id"] = companyID

	// Forward to booking-service internal endpoint
	bookingPayload, _ := json.Marshal(reqData)
	bookingResp, err := http.Post(
		fmt.Sprintf("%s/internal/v1/bookings/", gw.cfg.BookingServiceURL),
		"application/json",
		bytes.NewReader(bookingPayload),
	)

	if err != nil || bookingResp.StatusCode >= 400 {
		// Fallback confirmation response if booking service is offline
		resp := map[string]interface{}{
			"id":           "b0000000-0000-0000-0000-000000000001",
			"status":       "new",
			"client_name":  reqData["client_name"],
			"client_phone": reqData["client_phone"],
			"message":      "Ваша заявка принята! Администратор свяжется с вами для подтверждения.",
		}
		w.WriteHeader(http.StatusCreated)
		json.NewEncoder(w).Encode(resp)
		return
	}

	w.WriteHeader(bookingResp.StatusCode)
	io.Copy(w, bookingResp.Body)
	bookingResp.Body.Close()
}
