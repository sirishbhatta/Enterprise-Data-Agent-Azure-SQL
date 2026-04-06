#!/bin/bash
# DO NOT put pip install here - Azure already did it!
python -m streamlit run app.py --server.port=8080 --server.address=0.0.0.0 --server.headless=true