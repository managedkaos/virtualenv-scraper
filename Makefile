# Top-level Makefile that delegates to per-language sub-Makefiles.
# Executes targets sequentially, halting on first failure.

SUBDIRS_ALL := python rust go
SUBDIRS_BUILD := rust go

.PHONY: lint test build

lint:
	@for dir in $(SUBDIRS_ALL); do \
		$(MAKE) -C $$dir lint || { echo "Error: lint failed in $$dir" >&2; exit 1; }; \
	done

test:
	@for dir in $(SUBDIRS_ALL); do \
		$(MAKE) -C $$dir test || { echo "Error: test failed in $$dir" >&2; exit 1; }; \
	done

build:
	@for dir in $(SUBDIRS_BUILD); do \
		$(MAKE) -C $$dir build || { echo "Error: build failed in $$dir" >&2; exit 1; }; \
	done
