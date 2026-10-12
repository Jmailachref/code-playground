# Builds the static runbox helper that every language image copies in.
FROM gcc:14 AS build
COPY runbox.c /src/runbox.c
RUN gcc -O2 -static -o /runbox /src/runbox.c

FROM scratch
COPY --from=build /runbox /runbox
