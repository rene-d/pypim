default: x86

# build the standard server image
x86:
	docker build -t pypim .

# cross-compile an image for ARM
arm:
	docker build -t pypim -f Dockerfile.arm .

# build the image with certificates
secure: x86 server.crt server.key
	docker build -t pypim:secure -f Dockerfile.secure --squash .

# run http server in a Docker container
run:
	docker run --rm -ti -p 8000:8000 pypim

# run https server in a Docker container
run-secure: secure
	docker run --rm -ti -p 8000:8000 pypim:secure -secure

# create a self-signed certificated for 'localhost' host
# https://stackoverflow.com/questions/10175812/
server.crt server.key:
	openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes -keyout server.key -out server.crt -subj /CN=localhost
