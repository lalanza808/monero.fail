#!/bin/bash

git stash --
git pull origin main
bash stop.sh
bash start.sh