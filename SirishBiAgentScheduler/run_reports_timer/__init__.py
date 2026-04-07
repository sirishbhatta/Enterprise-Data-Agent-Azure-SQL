"""
run_reports_timer - Azure Function
====================================
This function is triggered by a timer and runs all the saved reports.
The reports are saved to Azure Blob Storage.
"""

import logging
import azure.functions as func
import datetime
import json
import os
import sys
from pathlib import Path
import pandas as pd

# Add shared code to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared_code"))
import db_connector as dbc


def main(mytimer: func.TimerRequest) -> None:
    utc_timestamp = datetime.datetime.utcnow().isoformat()

    if mytimer.past_due:
        logging.info('The timer is past due!')

    logging.info('Python timer trigger function ran at %s', utc_timestamp)

    # Get the directory of the function
    function_dir = Path(__file__).parent
    project_root = function_dir.parent.parent
    
    # Load reports from saved_reports.json
    reports_file = project_root / "saved_reports.json"
    if not reports_file.exists():
        logging.error(f"saved_reports.json not found at {reports_file}")
        return

    with open(reports_file, "r") as f:
        reports = json.load(f)

    if not reports:
        logging.info("No reports to run.")
        return

    # Get Azure Storage connection string from environment variables
    # AZURE_STORAGE_CONNECTION_STRING is a standard environment variable name
    # used by Azure Functions
    storage_connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not storage_connection_string:
        logging.error("AZURE_STORAGE_CONNECTION_STRING environment variable not set.")
        return

    # Name of the blob container
    container_name = "reports"

    from azure.storage.blob import BlobServiceClient

    try:
        blob_service_client = BlobServiceClient.from_connection_string(storage_connection_string)
        container_client = blob_service_client.get_container_client(container_name)
        container_client.create_container(fail_on_exist=False)
    except Exception as e:
        logging.error(f"Failed to connect to Blob Storage: {e}")
        return


    logging.info(f"Running {len(reports)} reports...")

    for report in reports:
        report_name = report.get("name", "Unnamed Report")
        sql = report.get("sql")

        if not sql:
            logging.warning(f"Report '{report_name}' has no SQL query. Skipping.")
            continue

        logging.info(f"Running report: {report_name}")

        try:
            # Execute query
            result_df = dbc.execute_query(sql, max_rows=5000)

            if result_df is not None and not result_df.empty:
                # Save the DataFrame to an in-memory Excel file
                output = pd.ExcelWriter(f"{report_name}.xlsx", engine='openpyxl')
                result_df.to_excel(output, index=False, sheet_name='Sheet1')
                output.close()
                
                # Get the binary data from the in-memory file
                with open(f"{report_name}.xlsx", 'rb') as f:
                    excel_data = f.read()

                # Upload to Blob Storage
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_name = report_name.replace(" ", "_").replace("/", "-")
                blob_name = f"{safe_name}_{ts}.xlsx"

                blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
                blob_client.upload_blob(excel_data, overwrite=True)

                logging.info(f"Successfully ran report '{report_name}' and saved to {blob_name} in container '{container_name}'.")
                
                # Clean up the local file
                os.remove(f"{report_name}.xlsx")

            else:
                logging.info(f"Report '{report_name}' returned no data.")

        except Exception as e:
            logging.error(f"Failed to run report '{report_name}': {e}")
    
    logging.info("Finished running all reports.")

