package main

import (
	"database/sql"
	"flag"
	"fmt"
	"log"
	"net/http"
	"strings"

	_ "github.com/mattn/go-sqlite3"
)

func simple(w http.ResponseWriter, r *http.Request) {
	log.Println("simple: ", r.RequestURI)
	//fmt.Fprint(w, "Welcome to my website!", r.RequestURI, "\n")

	path := strings.Split(r.URL.Path, "/")

	for i := 0; i < len(path); i++ {
		fmt.Printf("path[%d]=%s\n", i, path[i])
	}

	if paht[0] != "" || path[1] != "simple" {
		w.WriteHeader(404)
		return
	}

	project := path[2]
	db.Exec("select name,last_serial from package where name=?")

	w.WriteHeader(200)
}

func main() {

	// command line options
	port := flag.String("p", "8000", "port to serve on")
	directory := flag.String("d", "~/data/pypi", "the directory of static file to host")
	flag.Parse()

	db, err := sql.Open("sqlite3", "pypi.db")
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()

	http.Handle("/packages/", http.FileServer(http.Dir(*directory)))
	http.HandleFunc("/simple/", simple)

	log.Printf("Serving %s on HTTP port: %s\n", *directory, *port)

	log.Fatal(http.ListenAndServe(":"+*port, nil))
}
