package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/nurcrm/backend/libs/go_common/jwks"
	"github.com/nurcrm/backend/libs/go_common/redis"
	"github.com/nurcrm/backend/services/public-gateway/internal/availability"
)

type GatewayConfig struct {
	Port               string
	RedisAddr          string
	AuthServiceURL     string
	CatalogServiceURL  string
	ScheduleServiceURL string
	BookingServiceURL  string
}

func getEnv(key, defaultVal string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return defaultVal
}

type CompanyInfo struct {
	ID                   string `json:"id"`
	Name                 string `json:"name"`
	Slug                 string `json:"slug"`
	AppointmentWorkStart string `json:"appointment_work_start"`
	AppointmentWorkEnd   string `json:"appointment_work_end"`
	SubscriptionPlan     string `json:"subscription_plan"`
}

type PublicGateway struct {
	cfg     GatewayConfig
	redis   *redis.Client
	engine  *availability.AvailabilityEngine
	privKey []byte
	client  *http.Client
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

	privKey, err := jwks.LoadPrivateKey("")
	if err != nil {
		log.Printf("Warning: could not load private key at startup: %v", err)
	}

	rClient := redis.NewClient(cfg.RedisAddr, "", 0)
	gw := &PublicGateway{
		cfg:     cfg,
		redis:   rClient,
		engine:  availability.NewAvailabilityEngine(30),
		privKey: privKey,
		client:  &http.Client{Timeout: 5 * time.Second},
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
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, Idempotency-Key, X-Idempotency-Key")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusOK)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func (gw *PublicGateway) getInternalToken(targetService string) (string, error) {
	if len(gw.privKey) == 0 {
		var err error
		gw.privKey, err = jwks.LoadPrivateKey("")
		if err != nil {
			return "", fmt.Errorf("failed to load private key: %w", err)
		}
	}
	return jwks.CreateInternalToken("public-gateway", targetService, gw.privKey)
}

func (gw *PublicGateway) doInternalRequest(ctx context.Context, targetService, method, url string, body io.Reader, extraHeaders map[string]string) (*http.Response, error) {
	req, err := http.NewRequestWithContext(ctx, method, url, body)
	if err != nil {
		return nil, err
	}
	token, err := gw.getInternalToken(targetService)
	if err == nil && token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	req.Header.Set("Content-Type", "application/json")
	for k, v := range extraHeaders {
		req.Header.Set(k, v)
	}
	return gw.client.Do(req)
}

func (gw *PublicGateway) getCompanyBySlug(ctx context.Context, slug string) (*CompanyInfo, int, error) {
	// Try Redis cache
	cacheKey := fmt.Sprintf("pub:%s:company", slug)
	cachedBytes, err := gw.redis.Raw().Get(ctx, cacheKey).Bytes()
	if err == nil && len(cachedBytes) > 0 {
		var comp CompanyInfo
		if err := json.Unmarshal(cachedBytes, &comp); err == nil && comp.ID != "" {
			return &comp, http.StatusOK, nil
		}
	}

	url := fmt.Sprintf("%s/internal/v1/companies/slug/%s/", gw.cfg.AuthServiceURL, slug)
	resp, err := gw.doInternalRequest(ctx, "auth-service", http.MethodGet, url, nil, nil)
	if err != nil {
		log.Printf("Error contacting auth-service for slug %s: %v", slug, err)
		return nil, http.StatusBadGateway, fmt.Errorf("auth service unavailable: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNotFound {
		return nil, http.StatusNotFound, errors.New("company not found")
	}
	if resp.StatusCode >= 400 {
		return nil, resp.StatusCode, fmt.Errorf("auth service returned status %d", resp.StatusCode)
	}

	var comp CompanyInfo
	if err := json.NewDecoder(resp.Body).Decode(&comp); err != nil {
		return nil, http.StatusBadGateway, fmt.Errorf("invalid response from auth service: %w", err)
	}

	// Cache valid company in Redis for 5 minutes
	data, _ := json.Marshal(comp)
	_ = gw.redis.Raw().Set(ctx, cacheKey, data, 5*time.Minute).Err()

	return &comp, http.StatusOK, nil
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
	ctx, cancel := context.WithTimeout(r.Context(), 4*time.Second)
	defer cancel()

	comp, status, err := gw.getCompanyBySlug(ctx, slug)
	if err != nil {
		if status == http.StatusNotFound {
			http.Error(w, `{"code":"not_found","message":"Company not found"}`, http.StatusNotFound)
			return
		}
		http.Error(w, `{"code":"bad_gateway","message":"Failed to resolve company"}`, http.StatusBadGateway)
		return
	}

	url := fmt.Sprintf("%s/internal/v1/categories/?company_id=%s", gw.cfg.CatalogServiceURL, comp.ID)
	resp, err := gw.doInternalRequest(ctx, "catalog-service", http.MethodGet, url, nil, nil)
	if err != nil {
		log.Printf("Error contacting catalog-service for categories: %v", err)
		http.Error(w, `{"code":"bad_gateway","message":"Catalog service unavailable"}`, http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	w.WriteHeader(resp.StatusCode)
	io.Copy(w, resp.Body)
}

func (gw *PublicGateway) handleServices(w http.ResponseWriter, r *http.Request, slug string) {
	ctx, cancel := context.WithTimeout(r.Context(), 4*time.Second)
	defer cancel()

	comp, status, err := gw.getCompanyBySlug(ctx, slug)
	if err != nil {
		if status == http.StatusNotFound {
			http.Error(w, `{"code":"not_found","message":"Company not found"}`, http.StatusNotFound)
			return
		}
		http.Error(w, `{"code":"bad_gateway","message":"Failed to resolve company"}`, http.StatusBadGateway)
		return
	}

	cached, err := gw.redis.GetPublicServices(ctx, slug)
	if err == nil && len(cached) > 0 {
		w.Write(cached)
		return
	}

	url := fmt.Sprintf("%s/internal/v1/services/?company_id=%s", gw.cfg.CatalogServiceURL, comp.ID)
	resp, err := gw.doInternalRequest(ctx, "catalog-service", http.MethodGet, url, nil, nil)
	if err != nil {
		log.Printf("Error contacting catalog-service for services: %v", err)
		http.Error(w, `{"code":"bad_gateway","message":"Catalog service unavailable"}`, http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusOK {
		data, err := io.ReadAll(resp.Body)
		if err == nil {
			_ = gw.redis.SetPublicServices(ctx, slug, data, 300*time.Second)
			w.WriteHeader(http.StatusOK)
			w.Write(data)
			return
		}
	}

	w.WriteHeader(resp.StatusCode)
	io.Copy(w, resp.Body)
}

func (gw *PublicGateway) handleMasters(w http.ResponseWriter, r *http.Request, slug string) {
	ctx, cancel := context.WithTimeout(r.Context(), 4*time.Second)
	defer cancel()

	comp, status, err := gw.getCompanyBySlug(ctx, slug)
	if err != nil {
		if status == http.StatusNotFound {
			http.Error(w, `{"code":"not_found","message":"Company not found"}`, http.StatusNotFound)
			return
		}
		http.Error(w, `{"code":"bad_gateway","message":"Failed to resolve company"}`, http.StatusBadGateway)
		return
	}

	url := fmt.Sprintf("%s/internal/v1/masters/?company_id=%s", gw.cfg.AuthServiceURL, comp.ID)
	resp, err := gw.doInternalRequest(ctx, "auth-service", http.MethodGet, url, nil, nil)
	if err != nil {
		log.Printf("Error contacting auth-service for masters: %v", err)
		http.Error(w, `{"code":"bad_gateway","message":"Auth service unavailable"}`, http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	w.WriteHeader(resp.StatusCode)
	io.Copy(w, resp.Body)
}

func parseWorkHours(timeStr string, defaultH, defaultM int) (int, int) {
	if timeStr == "" {
		return defaultH, defaultM
	}
	parts := strings.Split(timeStr, ":")
	if len(parts) >= 2 {
		h, err1 := strconv.Atoi(parts[0])
		m, err2 := strconv.Atoi(parts[1])
		if err1 == nil && err2 == nil {
			return h, m
		}
	}
	return defaultH, defaultM
}

func (gw *PublicGateway) handleAvailability(w http.ResponseWriter, r *http.Request, slug string) {
	ctx, cancel := context.WithTimeout(r.Context(), 4*time.Second)
	defer cancel()

	comp, status, err := gw.getCompanyBySlug(ctx, slug)
	if err != nil {
		if status == http.StatusNotFound {
			http.Error(w, `{"code":"not_found","message":"Company not found"}`, http.StatusNotFound)
			return
		}
		http.Error(w, `{"code":"bad_gateway","message":"Failed to resolve company"}`, http.StatusBadGateway)
		return
	}

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

	// Dynamic work interval from company settings
	workStartH, workStartM := parseWorkHours(comp.AppointmentWorkStart, 9, 0)
	workEndH, workEndM := parseWorkHours(comp.AppointmentWorkEnd, 21, 0)

	var busyIntervals []availability.Interval
	if masterID != "" {
		url := fmt.Sprintf("%s/internal/v1/appointments/busy-slots/?company_id=%s&master_id=%s&date=%s",
			gw.cfg.ScheduleServiceURL, comp.ID, masterID, dateStr)
		resp, err := gw.doInternalRequest(ctx, "schedule-service", http.MethodGet, url, nil, nil)
		if err == nil && resp.StatusCode == http.StatusOK {
			var slots []struct {
				StartAt string `json:"start_at"`
				EndAt   string `json:"end_at"`
			}
			if err := json.NewDecoder(resp.Body).Decode(&slots); err == nil {
				for _, s := range slots {
					t1, err1 := time.Parse(time.RFC3339, s.StartAt)
					t2, err2 := time.Parse(time.RFC3339, s.EndAt)
					if err1 == nil && err2 == nil {
						busyIntervals = append(busyIntervals, availability.Interval{Start: t1, End: t2})
					}
				}
			}
			resp.Body.Close()
		}
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
	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
	defer cancel()

	bodyBytes, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, `{"code":"bad_request","message":"Failed to read body"}`, http.StatusBadRequest)
		return
	}

	var reqData map[string]interface{}
	if err := json.Unmarshal(bodyBytes, &reqData); err != nil {
		http.Error(w, `{"code":"validation_error","message":"Invalid JSON body"}`, http.StatusBadRequest)
		return
	}

	// 1. Resolve company by slug from auth-service
	comp, status, err := gw.getCompanyBySlug(ctx, slug)
	if err != nil {
		if status == http.StatusNotFound {
			http.Error(w, `{"code":"not_found","message":"Company not found"}`, http.StatusNotFound)
			return
		}
		http.Error(w, `{"code":"bad_gateway","message":"Failed to resolve company"}`, http.StatusBadGateway)
		return
	}

	reqData["company_id"] = comp.ID

	// 2. Forward to booking-service internal endpoint with signed token
	bookingPayload, err := json.Marshal(reqData)
	if err != nil {
		http.Error(w, `{"code":"internal_error","message":"Failed to serialize booking request"}`, http.StatusInternalServerError)
		return
	}

	extraHeaders := make(map[string]string)
	if idemp := r.Header.Get("Idempotency-Key"); idemp != "" {
		extraHeaders["Idempotency-Key"] = idemp
	} else if idemp := r.Header.Get("X-Idempotency-Key"); idemp != "" {
		extraHeaders["Idempotency-Key"] = idemp
	}

	bookingURL := fmt.Sprintf("%s/internal/v1/bookings/", gw.cfg.BookingServiceURL)
	bookingResp, err := gw.doInternalRequest(ctx, "booking-service", http.MethodPost, bookingURL, bytes.NewReader(bookingPayload), extraHeaders)
	if err != nil {
		log.Printf("Error contacting booking-service: %v", err)
		http.Error(w, `{"code":"bad_gateway","message":"Booking service unavailable"}`, http.StatusBadGateway)
		return
	}
	defer bookingResp.Body.Close()

	// 3. Transparently forward the response status and body from booking-service
	w.WriteHeader(bookingResp.StatusCode)
	io.Copy(w, bookingResp.Body)
}
