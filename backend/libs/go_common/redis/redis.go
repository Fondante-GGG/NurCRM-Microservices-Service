package redis

import (
	"context"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
)

type Client struct {
	rdb *redis.Client
}

func NewClient(addr, password string, db int) *Client {
	rdb := redis.NewClient(&redis.Options{
		Addr:     addr,
		Password: password,
		DB:       db,
	})
	return &Client{rdb: rdb}
}

func (c *Client) Raw() *redis.Client {
	return c.rdb
}

func (c *Client) Ping(ctx context.Context) error {
	return c.rdb.Ping(ctx).Err()
}

// Key format helpers
func KeyPublicServices(slug string) string {
	return fmt.Sprintf("pub:%s:services", slug)
}

func KeyPublicMasters(slug string) string {
	return fmt.Sprintf("pub:%s:masters", slug)
}

func KeyBusySlots(companyID, masterID, date string) string {
	return fmt.Sprintf("busy:%s:%s:%s", companyID, masterID, date)
}

func KeySoftLock(entity, entityID string) string {
	return fmt.Sprintf("edit:%s:%s", entity, entityID)
}

func KeyRateLimitIP(ip string) string {
	return fmt.Sprintf("rl:%s", ip)
}

func KeyRateLimitPhone(phone string) string {
	return fmt.Sprintf("rl:phone:%s", phone)
}

func (c *Client) SetPublicServices(ctx context.Context, slug string, data []byte, ttl time.Duration) error {
	return c.rdb.Set(ctx, KeyPublicServices(slug), data, ttl).Err()
}

func (c *Client) GetPublicServices(ctx context.Context, slug string) ([]byte, error) {
	return c.rdb.Get(ctx, KeyPublicServices(slug)).Bytes()
}

func (c *Client) AcquireSoftLock(ctx context.Context, entity, entityID, userID string, ttl time.Duration) (bool, error) {
	key := KeySoftLock(entity, entityID)
	return c.rdb.SetNX(ctx, key, userID, ttl).Result()
}

func (c *Client) GetSoftLockUser(ctx context.Context, entity, entityID string) (string, error) {
	key := KeySoftLock(entity, entityID)
	return c.rdb.Get(ctx, key).Result()
}

func (c *Client) ReleaseSoftLock(ctx context.Context, entity, entityID string) error {
	key := KeySoftLock(entity, entityID)
	return c.rdb.Del(ctx, key).Err()
}
