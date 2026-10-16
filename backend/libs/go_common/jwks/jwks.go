package jwks

import (
	"crypto/rsa"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"math/big"
	"net/http"
	"os"
	"sync"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

type Claims struct {
	CompanyID   string   `json:"company_id"`
	Role        string   `json:"role"`
	Permissions []string `json:"permissions"`
	SID         string   `json:"sid"`
	Email       string   `json:"email"`
	jwt.RegisteredClaims
}

type JWKSKey struct {
	Kty string `json:"kty"`
	Use string `json:"use"`
	Alg string `json:"alg"`
	Kid string `json:"kid"`
	N   string `json:"n"`
	E   string `json:"e"`
}

type JWKS struct {
	Keys []JWKSKey `json:"keys"`
}

type KeyValidator struct {
	jwksURL    string
	httpClient *http.Client
	mu         sync.RWMutex
	keys       map[string]*rsa.PublicKey
	lastFetch  time.Time
}

func NewKeyValidator(jwksURL string) *KeyValidator {
	return &KeyValidator{
		jwksURL:    jwksURL,
		httpClient: &http.Client{Timeout: 5 * time.Second},
		keys:       make(map[string]*rsa.PublicKey),
	}
}

func (v *KeyValidator) RefreshKeys() error {
	resp, err := v.httpClient.Get(v.jwksURL)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("unexpected status code fetching JWKS: %d", resp.StatusCode)
	}

	var jwks JWKS
	if err := json.NewDecoder(resp.Body).Decode(&jwks); err != nil {
		return err
	}

	newKeys := make(map[string]*rsa.PublicKey)
	for _, k := range jwks.Keys {
		if k.Kty != "RSA" || k.Alg != "RS256" {
			continue
		}
		pubKey, err := parseRSAPublicKey(k.N, k.E)
		if err == nil {
			newKeys[k.Kid] = pubKey
		}
	}

	v.mu.Lock()
	v.keys = newKeys
	v.lastFetch = time.Now()
	v.mu.Unlock()
	return nil
}

func (v *KeyValidator) SetKey(kid string, pubKey *rsa.PublicKey) {
	v.mu.Lock()
	defer v.mu.Unlock()
	v.keys[kid] = pubKey
}

func parseRSAPublicKey(nStr, eStr string) (*rsa.PublicKey, error) {
	nBytes, err := base64.RawURLEncoding.DecodeString(nStr)
	if err != nil {
		return nil, err
	}
	eBytes, err := base64.RawURLEncoding.DecodeString(eStr)
	if err != nil {
		return nil, err
	}

	n := new(big.Int).SetBytes(nBytes)
	var eInt int
	for _, b := range eBytes {
		eInt = (eInt << 8) | int(b)
	}

	return &rsa.PublicKey{
		N: n,
		E: eInt,
	}, nil
}

func (v *KeyValidator) ValidateToken(tokenStr string) (*Claims, error) {
	token, err := jwt.ParseWithClaims(tokenStr, &Claims{}, func(t *jwt.Token) (interface{}, error) {
		if _, ok := t.Method.(*jwt.SigningMethodRSA); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", t.Header["alg"])
		}

		kid, _ := t.Header["kid"].(string)
		v.mu.RLock()
		key, exists := v.keys[kid]
		v.mu.RUnlock()

		if !exists {
			if err := v.RefreshKeys(); err != nil {
				return nil, err
			}
			v.mu.RLock()
			key, exists = v.keys[kid]
			v.mu.RUnlock()
			if !exists {
				return nil, errors.New("key not found in JWKS")
			}
		}

		return key, nil
	})

	if err != nil {
		return nil, err
	}

	claims, ok := token.Claims.(*Claims)
	if !ok || !token.Valid {
		return nil, errors.New("invalid token claims")
	}

	return claims, nil
}

type InternalClaims struct {
	Iss  string `json:"iss"`
	Sub  string `json:"sub"`
	Aud  string `json:"aud"`
	Type string `json:"type"`
	jwt.RegisteredClaims
}

func LoadPrivateKey(path string) ([]byte, error) {
	if path == "" {
		path = os.Getenv("JWT_PRIVATE_KEY_PATH")
	}
	if path == "" {
		candidates := []string{
			"/app/keys/jwt_private.pem",
			"../../keys/jwt_private.pem",
			"../keys/jwt_private.pem",
			"keys/jwt_private.pem",
		}
		for _, p := range candidates {
			if _, err := os.Stat(p); err == nil {
				path = p
				break
			}
		}
	}
	if path == "" {
		return nil, errors.New("jwt_private.pem key file not found")
	}
	return os.ReadFile(path)
}

func CreateInternalToken(senderService, targetService string, privateKeyPEM []byte) (string, error) {
	key, err := jwt.ParseRSAPrivateKeyFromPEM(privateKeyPEM)
	if err != nil {
		return "", err
	}
	now := time.Now()
	claims := InternalClaims{
		Iss:  "nurcrm-mesh",
		Sub:  senderService,
		Aud:  targetService,
		Type: "internal",
		RegisteredClaims: jwt.RegisteredClaims{
			IssuedAt:  jwt.NewNumericDate(now),
			ExpiresAt: jwt.NewNumericDate(now.Add(5 * time.Minute)),
		},
	}
	token := jwt.NewWithClaims(jwt.SigningMethodRS256, claims)
	token.Header["kid"] = "nurcrm-default-key"
	return token.SignedString(key)
}

