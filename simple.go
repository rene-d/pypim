//
// simple HTTP server for pypi mirror
//
// pip usage:
//   pip3 install --index-url http://hostname:8000 --trusted-host hostname PROJECT ...
//

package main

import (
	"database/sql"
	"flag"
	"fmt"
	"html"
	"log"
	"net/http"
	"net/url"
	"regexp"
	"strconv"
	"strings"

	_ "github.com/mattn/go-sqlite3"
)

// the project database
var db *sql.DB

// returns normalized project name
func canonicalizeName(name string) string {
	name = strings.ToLower(name)
	re := regexp.MustCompile(`[-_.]+`)
	return re.ReplaceAllString(name, "-")
}

// returns the project list
func simpleIndex(w http.ResponseWriter) {

	fmt.Fprint(w, `<!DOCTYPE html>
<html>
  <head>
	<title>Simple index</title>
  </head>
  <body>
`)

	rows, _ := db.Query("select name from package order by name")
	defer rows.Close()
	for rows.Next() {
		var name string
		err := rows.Scan(&name)
		if err != nil {
			log.Fatal(err)
		}
		fmt.Fprintf(w, "    <a href=\"./%s\">%s</a><br/>\n", canonicalizeName(name), name)
	}

	fmt.Fprintf(w, `  </body>
  </html>
`)
}

// gets the files list for the given project
func simpleProject(w http.ResponseWriter, project string) {

	// verify if we have the project by fetching its last_serial
	var lastSerial int64
	err := db.QueryRow("select last_serial from package where name=?", project).Scan(&lastSerial)
	if err != nil {
		log.Printf("project %s not found", project)
		w.WriteHeader(403)
		return
	}

	filesCount := 0

	// build the html page with file list
	fmt.Fprintf(w, `<!DOCTYPE html>
<html>
  <head>
	<title>Links for %s</title>
  </head>
  <body>
	<h1>Links for %s</h1>
`, project, project)

	rows, _ := db.Query("select release,filename,url,size,requires_python,sha256_digest from file where name=?", project)
	defer rows.Close()
	for rows.Next() {
		var release string
		var filename string
		var fileURL string
		var size int64
		var requiresPython *string
		var sha256Digest string
		err := rows.Scan(&release, &filename, &fileURL, &size, &requiresPython, &sha256Digest)
		if err != nil {
			log.Println(err)
		} else {
			u, _ := url.Parse(fileURL)
			params := ""
			if requiresPython != nil {
				params = " data-requires-python=\"" + html.EscapeString(*requiresPython) + "\""
			}
			fmt.Fprintf(w, "    <a href=\"../..%s#sha256=%s\"%s>%s</a><br/>\n", u.Path, sha256Digest, params, filename)

			filesCount++
		}
	}

	fmt.Fprintf(w, `  </body>
</html>
<!--SERIAL {%d}-->`, lastSerial)

	fmt.Printf("project %s : last_serial=%d files=%d\n", project, lastSerial, filesCount)
}

func simple(w http.ResponseWriter, r *http.Request) {

	// request URL is /simple/xxxx/...
	// project name is the third element
	path := strings.Split(r.URL.Path, "/")

	if path[2] == "" {
		simpleIndex(w)
	} else {
		simpleProject(w, canonicalizeName(path[2]))
	}
}

func defaultHandle(w http.ResponseWriter, r *http.Request) {
	log.Println(">>>", r.RequestURI)

	fmt.Fprintln(w, "Hello from Go!")

	fmt.Fprintln(w, "URL:", r.URL)
	fmt.Fprintln(w, "RemoteAddr:", r.RemoteAddr)
	fmt.Fprintln(w, "Method:", r.Method)
	fmt.Fprintln(w, "Proto:", r.Proto)
	fmt.Fprintln(w, "Host:", r.Host)
	fmt.Fprintln(w, "Headers:")
	for name, headers := range r.Header {
		for _, h := range headers {
			fmt.Fprintf(w, "  %v: %v\n", name, h)
		}
	}
}

func main() {

	// command line options
	port := flag.Int("p", 8000, "port to serve on")
	directory := flag.String("web", "~/data/pypi", "mirror directory")
	database := flag.String("db", "pypi.db", "project database")
	flag.Parse()

	var err error
	db, err = sql.Open("sqlite3", *database)
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()

	http.Handle("/packages/", http.FileServer(http.Dir(*directory)))
	http.HandleFunc("/simple/", simple)
	http.HandleFunc("/", defaultHandle)

	addr := ":" + strconv.Itoa(*port)

	log.Printf("Serving %s on HTTP port: %d", *directory, *port)
	log.Fatal(http.ListenAndServe(addr, nil))

	/*
		Generate private key (.key)

			# Key considerations for algorithm "RSA" ≥ 2048-bit
			openssl genrsa -out server.key 2048

			# Key considerations for algorithm "ECDSA" (X25519 || ≥ secp384r1)
			# https://safecurves.cr.yp.to/
			# List ECDSA the supported curves (openssl ecparam -list_curves)
			openssl ecparam -genkey -name secp384r1 -out server.key

		Generation of self-signed(x509) public key (PEM-encodings .pem|.crt) based on the private (.key)

			openssl req -new -x509 -sha256 -key server.key -out server.crt -days 3650
	*/

	// log.Printf("Serving %s on HTTPS port: %d", *directory, *port)
	// log.Fatal(http.ListenAndServeTLS(addr, "server.crt", "server.key", nil))
}
