.PHONY: all print-version image image-publish

all: image

DOCKER ?= docker
GIT ?= git

CURRENT_SHA ?= $(shell $(GIT) rev-parse --short HEAD)

IMAGE_NAME ?= registry.gitlab.com/mrman/localstripe
# Image version is updated manually to match latest version of adrianverge/localstripe that has been  merged
IMAGE_VERSION ?= $(shell grep '__version__' localstripe/__init__.py | cut -d"'" -f2)
IMAGE_FULL_NAME_SHA ?= $(IMAGE_NAME):$(IMAGE_VERSION)-$(CURRENT_SHA)
IMAGE_FULL_NAME ?= $(IMAGE_NAME):$(IMAGE_VERSION)

print-version:
	@echo -e -n "$(IMAGE_VERSION)"

image:
	$(DOCKER) build -t $(IMAGE_FULL_NAME_SHA) .

image-publish: image
	$(DOCKER) tag $(IMAGE_FULL_NAME_SHA) $(IMAGE_FULL_NAME)
	$(DOCKER) push $(IMAGE_FULL_NAME)
