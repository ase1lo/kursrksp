.PHONY: run test coverage docker-build

run:
	python3 -m server.httpd

test:
	python3 -m unittest discover -v

coverage:
	python3 scripts/coverage_gate.py

docker-build:
	docker build -t corplink-messenger .
