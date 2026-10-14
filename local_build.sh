#!/usr/bin/env bash

python3 -m pylint --load-plugins=pylint_django \
  --django-settings-module=hairdresser_django.settings \
  --ignore=migrations --ignore-patterns=".*~.*" appointments/

python3 -m coverage run --source=. manage.py test appointments
python3 -m coverage report -m
python3 -m coverage html