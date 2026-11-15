web: python -c "import dados; dados.baixar_se_preciso()" && gunicorn app:server --workers 1 --threads 8 --timeout 120 --bind 0.0.0.0:$PORT
