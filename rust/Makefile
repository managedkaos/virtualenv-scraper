.PHONY: lint test build

lint:
	cargo clippy -- -D warnings
	cargo fmt --check

test:
	cargo test

build:
	cargo build --release
