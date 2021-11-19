#!/bin/sh

gunicorn -b 0.0.0.0:8000 --pid pid --timeout 600 --workers=4 app:api