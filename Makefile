.PHONY: install lint catalog test check links

install:
	npm ci

lint:
	npm run lint:awesome

catalog:
	python3 tools/catalog.py README.md

test:
	python3 -m unittest discover -s tests -v

check: lint catalog test

links:
	lychee --config .lychee.toml README.md CONTRIBUTING.md EDITORIAL.md
