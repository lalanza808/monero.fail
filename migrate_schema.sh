#!/bin/bash
xmrnodes
#
sqlite3 data/sqlite.db "SELECT * from node;" > /dev/null

# backup database
cp data/sqlite.db data/backup.sqlite

# rename table
sqlite3 data/sqlite.db "ALTER TABLE node RENAME TO old_node;"

# init table
./manage.sh init

# move data
sqlite3 data/sqlite.db "INSERT INTO node SELECT * FROM old_node;"