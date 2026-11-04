#!/bin/sh
set -eu
exec /usr/bin/python3 /etc/isurvix-staging/ingress/renew_tls.py --config /etc/isurvix-staging/ingress/renewal-config.json
