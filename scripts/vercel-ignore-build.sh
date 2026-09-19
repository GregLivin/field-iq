#!/usr/bin/env bash
# Vercel Ignored Build Step.
# Exit 0 = skip deployment; exit 1 = continue deployment.
# Data/model-only bot commits are validated and stored by GitHub Actions and do
# not need a new frontend/API deployment.
set -eu

if git log -1 --pretty=%B | grep -q '^Update daily NFL data and predictions$'; then
  echo "Skipping Vercel build for automated Field IQ data refresh."
  exit 0
fi

echo "Application/code change detected; continue Vercel build."
exit 1
