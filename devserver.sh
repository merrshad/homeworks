#!/bin/sh
source .venv/bin/activate
flask db upgrade
python -m flask --app main run -p $PORT --debug