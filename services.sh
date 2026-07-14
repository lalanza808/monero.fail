#!/bin/bash

set -e

usage() {
  echo "Usage: $0 {start|stop|update}"
  exit 1
}

do_start() {
  set -x
  sudo service monero start
  sudo service onion start
}

do_stop() {
  set -x
  sudo service monero stop
  sudo service onion stop
}

do_update() {
  git stash --
  git pull origin main
  do_stop
  do_start
}

case "${1}" in
  start)  do_start ;;
  stop)   do_stop ;;
  update) do_update ;;
  *)      usage ;;
esac
