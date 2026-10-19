#!/bin/bash
cd "/Users/jhanzeebakbar/Scalp Indicator V1"
echo "Starting chart server on http://localhost:8000"
echo "Serving Section 11's chart UI"
echo "Press Ctrl+C to stop."
echo
exec python3 -u -m Section_11_UI_UX.server.ui_server
