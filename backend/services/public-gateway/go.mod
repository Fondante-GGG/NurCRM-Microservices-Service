module github.com/nurcrm/backend/services/public-gateway

go 1.22

require github.com/nurcrm/backend/libs/go_common v0.0.0

require (
	github.com/cespare/xxhash/v2 v2.2.0 // indirect
	github.com/dgryski/go-rendezvous v0.0.0-20200823014737-9f7001d12a5f // indirect
	github.com/redis/go-redis/v9 v9.5.1 // indirect
)

replace github.com/nurcrm/backend/libs/go_common => ../../libs/go_common
