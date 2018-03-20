version 		:= 0.0.1
image-name 	:= localstripe
dockerID 		:= kerak19
target			:= $(dockerID)/$(image-name)
target-ver  := $(target):$(version)

all: build

docker-push: docker-build
	docker push $(target):latest
	docker push $(target-ver)

docker-build:
	docker build -t $(target) -t $(target-ver) .