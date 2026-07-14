#!/bin/bash

chown -R i2pd:i2pd /var/lib/i2pd

# Run i2pd
sudo -u i2pd i2pd \
    --loglevel=error \
    --httpproxy.enabled 1 \
    --httpproxy.address 0.0.0.0 \
    --httpproxy.port 4444
