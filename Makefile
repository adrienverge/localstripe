DEFAULT_PORT := "8420"
PORT := "12111"

run:
	poetry run python -m localstripe ${PORT}

requirements:
	poetry export -f requirements.txt --output requirements.txt --without-hashes

test:
	./test.sh

test-auto:
	poetry run python -m localstripe &
	pid="$!"
	@echo "Waiting 2 seconds for the server to start..."
	sleep 2
	./test.sh
	kill "$pid"

docker-build: requirements
	docker build . -t cap-localstripe

docker-run:
	docker run --rm -it -p ${PORT}:${DEFAULT_PORT} cap-localstripe:latest
