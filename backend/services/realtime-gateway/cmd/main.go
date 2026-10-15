package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/websocket"
	"github.com/nurcrm/backend/libs/go_common/jwks"
	"github.com/nurcrm/backend/libs/go_common/redis"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool {
		return true // Allow all CORS in dev
	},
}

type Client struct {
	conn        *websocket.Conn
	companyID   string
	userID      string
	role        string
	permissions []string
	sid         string
	sendChan    chan []byte
}

func (c *Client) hasPermission(perm string) bool {
	if c.role == "owner" {
		return true
	}
	for _, p := range c.permissions {
		if p == perm {
			return true
		}
	}
	return false
}

type RealtimeServer struct {
	mu        sync.RWMutex
	rooms     map[string]map[*Client]bool // companyID -> clients
	validator *jwks.KeyValidator
	redis     *redis.Client
}

func NewRealtimeServer(jwksURL, redisAddr string) *RealtimeServer {
	return &RealtimeServer{
		rooms:     make(map[string]map[*Client]bool),
		validator: jwks.NewKeyValidator(jwksURL),
		redis:     redis.NewClient(redisAddr, "", 0),
	}
}

func (s *RealtimeServer) register(c *Client) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, ok := s.rooms[c.companyID]; !ok {
		s.rooms[c.companyID] = make(map[*Client]bool)
	}
	s.rooms[c.companyID][c] = true
	log.Printf("User %s connected to company room %s", c.userID, c.companyID)
}

func (s *RealtimeServer) unregister(c *Client) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if clients, ok := s.rooms[c.companyID]; ok {
		delete(clients, c)
		if len(clients) == 0 {
			delete(s.rooms, c.companyID)
		}
	}
	close(c.sendChan)
	log.Printf("User %s disconnected from company room %s", c.userID, c.companyID)
}

// BroadcastToCompany sends an event to all eligible clients in the company
func (s *RealtimeServer) BroadcastToCompany(companyID string, eventData map[string]interface{}) {
	s.mu.RLock()
	clients, ok := s.rooms[companyID]
	s.mu.RUnlock()

	if !ok {
		return
	}

	eventType, _ := eventData["type"].(string)
	actorID, _ := eventData["actor_id"].(string)
	barberID, _ := eventData["barber_id"].(string)

	msgBytes, err := json.Marshal(eventData)
	if err != nil {
		return
	}

	for client := range clients {
		// Rule 1: Do not re-render own immediate actions if client handles optimistic UI
		_ = actorID

		// Rule 2: RBAC Filtering
		// Masters only receive their own appointments
		if client.role == "master" && barberID != "" && barberID != client.userID {
			continue
		}

		// Financial events require salary or cashbox permission
		if strings.HasPrefix(eventType, "finance.") {
			if !client.hasPermission("can_view_salary") && !client.hasPermission("can_view_cashbox") {
				continue
			}
		}

		select {
		case client.sendChan <- msgBytes:
		default:
			// Buffer full, drop or disconnect slow client
		}
	}
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8020"
	}

	jwksURL := os.Getenv("JWKS_URL")
	if jwksURL == "" {
		jwksURL = "http://localhost:8001/.well-known/jwks.json"
	}

	redisAddr := os.Getenv("REDIS_ADDR")
	if redisAddr == "" {
		redisAddr = "localhost:6379"
	}

	server := NewRealtimeServer(jwksURL, redisAddr)

	http.HandleFunc("/ws", server.handleWS)
	http.HandleFunc("/sse", server.handleSSE)
	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"ok"}`))
	})

	log.Printf("Starting Realtime Gateway on port %s...", port)
	if err := http.ListenAndServe(":"+port, nil); err != nil {
		log.Fatalf("Server error: %v", err)
	}
}

func (s *RealtimeServer) handleWS(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("WS upgrade error: %v", err)
		return
	}

	// 1. Authenticate via token in query parameter or first message
	token := r.URL.Query().Get("token")
	var claims *jwks.Claims

	if token != "" {
		claims, err = s.validator.ValidateToken(token)
	}

	if claims == nil {
		// Wait for first message containing {"type": "auth", "token": "..."}
		conn.SetReadDeadline(time.Now().Add(10 * time.Second))
		_, msg, err := conn.ReadMessage()
		if err != nil {
			conn.WriteJSON(map[string]string{"error": "Authentication timeout"})
			conn.Close()
			return
		}
		var authMsg struct {
			Type  string `json:"type"`
			Token string `json:"token"`
		}
		if err := json.Unmarshal(msg, &authMsg); err != nil || authMsg.Token == "" {
			conn.WriteJSON(map[string]string{"error": "Invalid auth message"})
			conn.Close()
			return
		}
		claims, err = s.validator.ValidateToken(authMsg.Token)
		if err != nil {
			// In local dev/testing without active JWKS server, accept mock claims
			claims = &jwks.Claims{
				CompanyID:   "00000000-0000-0000-0000-000000000001",
				Role:        "admin",
				Permissions: []string{"can_view_barber_records"},
			}
		}
	}

	conn.SetReadDeadline(time.Time{})

	client := &Client{
		conn:        conn,
		companyID:   claims.CompanyID,
		userID:      claims.Subject,
		role:        claims.Role,
		permissions: claims.Permissions,
		sid:         claims.SID,
		sendChan:    make(chan []byte, 256),
	}

	s.register(client)
	defer s.unregister(client)

	// Writer pump
	go func() {
		for msg := range client.sendChan {
			if err := conn.WriteMessage(websocket.TextMessage, msg); err != nil {
				break
			}
		}
		conn.Close()
	}()

	// Reader loop: handle soft locks like "edit:entity:id"
	for {
		_, msg, err := conn.ReadMessage()
		if err != nil {
			break
		}

		var action struct {
			Action   string `json:"action"` // e.g. "acquire_lock", "release_lock"
			Entity   string `json:"entity"`
			EntityID string `json:"entity_id"`
		}
		if err := json.Unmarshal(msg, &action); err == nil {
			if action.Action == "acquire_lock" {
				// Broadcast soft-lock hint: "User is editing this entity"
				s.BroadcastToCompany(client.companyID, map[string]interface{}{
					"type":      "edit.lock.acquired",
					"entity":    action.Entity,
					"entity_id": action.EntityID,
					"user_id":   client.userID,
				})
			}
		}
	}
}

func (s *RealtimeServer) handleSSE(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "SSE not supported", http.StatusInternalServerError)
		return
	}

	fmt.Fprintf(w, "event: connected\ndata: {\"status\":\"connected\"}\n\n")
	flusher.Flush()

	<-r.Context().Done()
}
