#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
exec "$ROOT/resources/skills/research-library/scripts/research-store" source-add "$@"
