# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import signal
import sys
from types import FrameType
from io import BytesIO, StringIO
import zipfile
from collections import defaultdict

import o365AuditParser

from flask import Flask, send_file, request
import werkzeug


from utils.logging import logger

app = Flask(__name__)


@app.route("/oldhello")
def hello() -> str:
    # Use basic logging with custom fields
    logger.info(logField="custom-entry", arbitraryField="custom-entry")

    # https://cloud.google.com/run/docs/logging#correlate-logs
    logger.info("Child logger with trace Id.")

    return "Hello, World!"

@app.route('/')
def show_form():
    return '''
        <form action="/process_file" method="post" enctype="multipart/form-data">
          <input type="file" name="file">
          <input type="submit" value="Upload">
        </form>
    '''

@app.route('/process_file', methods=['POST'])
def process_file():
    # Get the file from the POST request
    file = request.files['file']

    # convert werkzeug FileStorage to StringIO
    file_data = StringIO(file.read().decode('utf-8'))
    file.close()

    #dicts to hold record field names and parsed results
    fieldNames = defaultdict(set)
    results = defaultdict(list)

    results, fieldNames = o365AuditParser.process_file(file_data, results, fieldNames)

    csv_dict = o365AuditParser.workload_csv_stringio(results, fieldNames)


    zip_file = create_zipfile(csv_dict)
    zip_file.seek(0)

    # Send the file to the user with the appropriate headers
    return send_file(zip_file, mimetype='application/zip', attachment_filename='files.zip')

def create_zipfile(file_dict):
    # returns an IO object containing a .zip file.
    # the contents of the .zip are the input dictionary
    # dictionary keys are understood to be filenames, dictionary values are expected to be 
    # file contents
    # Create a zipfile containing the multiple files
    zip_file_IO = BytesIO()
    with zipfile.ZipFile(zip_file_IO, mode='w') as zf:
        for filename in file_dict.keys():
            logger.info(filename)
            zf.writestr(filename, file_dict[filename].getvalue())

    return zip_file_IO


def shutdown_handler(signal_int: int, frame: FrameType) -> None:
    logger.info(f"Caught Signal {signal.strsignal(signal_int)}")

    from utils.logging import flush

    flush()

    # Safely exit program
    sys.exit(0)


if __name__ == "__main__":
    # Running application locally, outside of a Google Cloud Environment

    # handles Ctrl-C termination
    signal.signal(signal.SIGINT, shutdown_handler)

    app.run(host="localhost", port=8080, debug=True)
else:
    # handles Cloud Run container termination
    signal.signal(signal.SIGTERM, shutdown_handler)
