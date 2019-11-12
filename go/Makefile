# Makefile for simple.go

default:
	@echo "Use « make <TAB> » to get the target list"

all: simple simple.linux simple.arm

simple: simple.go statik
	go build simple.go

.PHONY: statik
statik:
	statik -c "static resources"

# build the standard server image
.PHONY: x86 docker linux
x86 docker linux:
	docker build -q -t pypim .

# cross-compile an image for ARM
.PHONY:	arm
arm:
	docker build -q -t pypim:arm -f Dockerfile.arm .

# build the image with certificates
.PHONY:	secure
secure: x86 server.crt server.key
	docker build -q -t pypim:secure -f Dockerfile.secure --squash .

# run http server in a Docker container
.PHONY:	run
run: x86
	docker run --rm -ti -p 8000:8000 -v ~/data/pypi:/data pypim

# run https server in a Docker container
.PHONY:	run-secure
run-secure: secure
	docker run --rm -ti -p 8000:8000 -v ~/data/pypi:/data pypim:secure -secure

# create a self-signed certificated for 'localhost' host
# https://stackoverflow.com/questions/10175812/
server.crt server.key:
	openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes -keyout server.key -out server.crt -subj /CN=localhost

# extract linux x86 executable from Docker image
create_id = $(shell docker create pypim)
set_id = $(eval container_id=$(create_id))
simple.linux: x86
	@$(set_id)
	@echo "Container filesystem:"
	@docker export $(container_id) | tar -tv
	docker export $(container_id) | tar -xO simple > simple.linux
	docker container rm $(container_id)
	chmod a+x simple.linux

# extract linux arm executable from Docker image
create_id_arm = $(shell docker create pypim:arm)
set_id_arm = $(eval container_id_arm=$(create_id_arm))
simple.arm: arm
	@$(set_id_arm)
	@echo "Container filesystem:"
	@docker export $(container_id_arm) | tar -tv
	docker export $(container_id_arm) | tar -xO simple > simple.arm
	docker container rm $(container_id_arm)
	chmod a+x simple.arm

clean:
	docker container prune -f
	docker image prune -f
	rm -rf simple.arm simple.linux server.crt server.key simple statik
