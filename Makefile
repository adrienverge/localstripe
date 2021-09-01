.PHONY: all image image-publish

all: image

DOCKER ?= docker
IMAGE_NAME ?= registry.gitlab.com/mrman/localstripe
# Image version is updated manually to match latest version of adrianverge/localstripe that has been  merged
IMAGE_VERSION ?= 1.13.0
IMAGE_FULL_NAME ?= $(IMAGE_NAME):$(IMAGE_VERSION)

image:
	$(DOCKER) build -t $(IMAGE_FULL_NAME) .

image-publish: image
	$(DOCKER) push $(IMAGE_FULL_NAME)