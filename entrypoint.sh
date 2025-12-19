#!/bin/sh
set -e

mkdir -p /dados/embeddings/votebem || true
mkdir -p /dados/chroma || true
mkdir -p /dados/votebem/docs/noticias || true

exec "$@"
