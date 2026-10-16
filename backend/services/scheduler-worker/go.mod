module github.com/nurcrm/backend/services/scheduler-worker

go 1.22

require (
	github.com/lib/pq v1.10.9
	github.com/nurcrm/backend/libs/go_common v0.0.0
)

require github.com/golang-jwt/jwt/v5 v5.2.1 // indirect

replace github.com/nurcrm/backend/libs/go_common => ../../libs/go_common
