#!/bin/bash
# Run the Streamlit dashboard

echo "Starting EV Charging Grid Optimizer Dashboard..."
echo "Opening at: http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop"
echo ""

streamlit run app.py --theme.base dark --theme.primaryColor "#10b981" --theme.secondaryBackgroundColor "#1f2937"
