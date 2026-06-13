.PHONY: lint test build

lint:
	golangci-lint run ./...

test:
	go test ./...

build:
	go build -o bin/virtualenv-viewer ./cmd/virtualenv-viewer
