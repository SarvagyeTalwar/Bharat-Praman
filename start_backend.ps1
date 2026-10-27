# Starts the Bharat Praman backend on Python 3.14.
# MHA defaults to the complete local TF-IDF + full-text index. The optional
# e5 path needs torch + sentence-transformers, which have no working wheels on
# Python 3.15. Running with `python` may silently select 3.15.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
py -3.14 -m uvicorn main:app --host 127.0.0.1 --port 8000
