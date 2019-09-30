FROM golang AS builder

RUN go get -v github.com/mattn/go-sqlite3

COPY *.go /go/

# https://github.com/golang/go/issues/26492
RUN env CGO_ENABLED=1 CGO_CFLAGS="-DSQLITE_OMIT_LOAD_EXTENSION" \
    go build -tags "netgo sqlite_omit_load_extension" -ldflags '-s -w -extldflags "-static"' -o simple simple.go

FROM scratch
COPY --from=builder /go/simple /simple
ENTRYPOINT ["/simple", "-r", "/data"]
