.PHONY: image

all: image

DOCKER ?= docker
IMAGE_NAME ?= registry.gitlab.com/mrman/localstripe
IMAGE_VERSION ?= 1.12.7
IMAGE_FULL_NAME ?= $(IMAGE_NAME):$(IMAGE_VERSION)

image:
	$(DOCKER) build -t $(IMAGE_FULL_NAME) .
