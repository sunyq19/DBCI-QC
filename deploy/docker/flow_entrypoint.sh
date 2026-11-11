#!/bin/sh
set -eu
if [ -s /config/password.verifier ]; then
    export FLOW_PASSWORD_FILE=/config/password.verifier
else
    unset FLOW_PASSWORD_FILE
fi
exec "$@"
