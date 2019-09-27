FROM golang AS builder

RUN apt-get update -y \
&&  apt-get install -y apt-utils gcc-8-arm-linux-gnueabihf

RUN go get -v github.com/mattn/go-sqlite3

COPY *.go /go/

RUN env CC=arm-linux-gnueabihf-gcc-8 CXX=arm-linux-gnueabihf-g++-8 \
        CGO_ENABLED=1 GOOS=linux GOARCH=arm GOARM=7 \
        CGO_CFLAGS="-DSQLITE_OMIT_LOAD_EXTENSION" \
    go build -tags "netgo sqlite_omit_load_extension" -ldflags '-extldflags "-static"' -o simple.arm simple.go

# https://github.com/golang/go/issues/26492
RUN env CGO_ENABLED=1 CGO_CFLAGS="-DSQLITE_OMIT_LOAD_EXTENSION" \
    go build -tags "netgo sqlite_omit_load_extension" -ldflags '-extldflags "-static"' -o simple simple.go

FROM scratch
COPY --from=builder /go/simple /simple
ENTRYPOINT ["/simple"]
