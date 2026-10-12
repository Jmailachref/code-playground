FROM golang:1.23
COPY --from=codeplay/runbox:latest /runbox /usr/local/bin/runbox
# Pre-build the standard library into a cache so a submission compiles in
# about a second; the sandbox copies it into its writable /tmp at start.
ENV GOCACHE=/opt/gocache GOFLAGS=-buildvcs=false GOTOOLCHAIN=local
RUN mkdir -p /tmp/warm && cd /tmp/warm \
 && printf 'package main\nimport (\n"bufio"\n"fmt"\n"math"\n"os"\n"sort"\n"strconv"\n"strings"\n)\nfunc main(){r:=bufio.NewReader(os.Stdin);var s string;fmt.Fscan(r,&s);x,_:=strconv.Atoi(s);a:=[]int{x};sort.Ints(a);fmt.Println(strings.ToUpper(s),math.Sqrt(2),a)}\n' > main.go \
 && go build -o main main.go && rm -rf /tmp/warm && chmod -R a+rX /opt/gocache
ENV GOCACHE=/tmp/gocache HOME=/tmp
WORKDIR /code
