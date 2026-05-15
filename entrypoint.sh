#!/bin/bash

set -e

echo "Iniciando frontend..."

cd /development/index-interface
npm start &

echo "Iniciando backend..."

cd /development/index-backend
exec npm run dev
