#!/bin/bash

docker run \
  --rm -it --name grafana \
  -p 3333:3000 \
  --user 1000:1000 \
  -v ./db:/data \
  -v ./data:/var/lib/grafana \
  grafana/grafana
