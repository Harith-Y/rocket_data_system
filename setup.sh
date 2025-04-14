#!/bin/bash
set -e

echo "Running database initialization..."
python init_db.py

echo "Creating upload directory..."
mkdir -p static/uploads

echo "Setup completed successfully!"
