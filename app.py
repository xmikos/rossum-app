import os
import base64
import logging
import typing
from typing import Any, AsyncIterator

from flask import Flask, request, jsonify, Response
from functools import wraps
from rossum_api.api_client import APIClient
from rossum_api.elis_api_client import ExportFileFormats
from rossum_api.domain_logic.resources import Resource
import xml.etree.ElementTree as ET
import aiohttp

# Load .env file
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables for authentication
USERNAME = os.getenv("APP_USERNAME")
PASSWORD = os.getenv("APP_PASSWORD")
ROSSUM_USERNAME = os.getenv("ROSSUM_USERNAME")
ROSSUM_PASSWORD = os.getenv("ROSSUM_PASSWORD")
ROSSUM_BASE_URL = os.getenv("ROSSUM_BASE_URL", "https://mktest.rossum.app/api/v1")
POSTBIN_URL = os.getenv("POSTBIN_URL", "https://www.postb.in/1734582865900-7316913648974")


def check_auth(username: str, password: str) -> bool:
    """Check if the provided username and password match the expected credentials.

    Args:
        username (str): Username from the request.
        password (str): Password from the request.

    Returns:
        bool: True if credentials are valid, False otherwise.
    """
    return username == USERNAME and password == PASSWORD


def authenticate() -> Response:
    """Sends a 401 response that enables basic auth.

    Returns:
        Response: Flask response object with 401 status.
    """
    return Response(
        'Auth failed!',
        401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )


def requires_auth(f):
    """Decorator to enforce Basic Authentication on endpoints.

    Args:
        f (function): The Flask view function.

    Returns:
        function: The decorated function.
    """
    @wraps(f)
    async def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return await f(*args, **kwargs)
    return decorated


def convert_xml(input_xml: str) -> str:
    """Convert the input XML from Rossum format to the desired XML format.

    Args:
        input_xml (str): Original XML string from Rossum.

    Returns:
        str: Converted XML string.
    """
    root = ET.fromstring(input_xml)
    annotation = root.find('.//annotation')
    content = annotation.find('content')

    # Extract data points
    try:
        invoice_number = content.find(".//datapoint[@schema_id='invoice_id']").text
    except AttributeError:
        invoice_number = content.find(".//datapoint[@schema_id='document_id']").text
    invoice_date = content.find(".//datapoint[@schema_id='date_issue']").text + "T00:00:00"
    due_date = content.find(".//datapoint[@schema_id='date_due']").text + "T00:00:00"
    iban = content.find(".//datapoint[@schema_id='iban']").text
    currency = content.find(".//datapoint[@schema_id='currency']").text.upper()
    vendor = content.find(".//datapoint[@schema_id='sender_name']").text
    vendor_address = content.find(".//datapoint[@schema_id='sender_address']").text
    amount_total_tax = content.find(".//datapoint[@schema_id='amount_total_tax']").text
    amount_total_base = content.find(".//datapoint[@schema_id='amount_total_base']").text
    amount_total = content.find(".//datapoint[@schema_id='amount_total']").text

    # Populate Payable
    payable = ET.Element('Payable')
    ET.SubElement(payable, 'InvoiceNumber').text = invoice_number
    ET.SubElement(payable, 'InvoiceDate').text = invoice_date
    ET.SubElement(payable, 'DueDate').text = due_date
    ET.SubElement(payable, 'TotalAmount').text = amount_total
    ET.SubElement(payable, 'Notes')  # Empty Notes
    ET.SubElement(payable, 'Iban').text = iban
    ET.SubElement(payable, 'Amount').text = amount_total_base
    ET.SubElement(payable, 'Currency').text = currency
    ET.SubElement(payable, 'Vendor').text = vendor
    ET.SubElement(payable, 'VendorAddress').text = vendor_address

    # Details
    details = ET.SubElement(payable, 'Details')
    line_items = content.findall(".//tuple[@schema_id='line_item']")

    for idx, item in enumerate(line_items, start=1):
        detail = ET.SubElement(details, 'Detail')
        amount = item.find(".//datapoint[@schema_id='item_amount']").text
        quantity = item.find(".//datapoint[@schema_id='item_quantity']").text
        notes = item.find(".//datapoint[@schema_id='item_description']").text or f"Line item {idx}"
        ET.SubElement(detail, 'Amount').text = amount
        ET.SubElement(detail, 'AccountId')  # Empty AccountId
        ET.SubElement(detail, 'Quantity').text = quantity
        ET.SubElement(detail, 'Notes').text = notes

    invoices = ET.Element('Invoices')
    invoices.append(payable)
    invoice_registers = ET.Element('InvoiceRegisters')
    invoice_registers.append(invoices)

    xml_declaration = '<?xml version="1.0" encoding="utf-8"?>\n'
    converted_xml = xml_declaration + ET.tostring(invoice_registers, encoding='unicode')
    return converted_xml


async def export_annotations_to_file(
    client: APIClient, queue_id: int, export_format: ExportFileFormats, **filters: Any
) -> AsyncIterator[bytes]:
    """https://elis.rossum.ai/api/docs/#export-annotations.

    XLSX/CSV/XML exports can be huge, therefore byte streaming is used to keep memory consumption low.
    """
    async for chunk in client.export(Resource.Queue, queue_id, str(export_format), **filters):
        yield typing.cast(bytes, chunk)


@app.route('/export', methods=['GET'])
@requires_auth
async def export() -> Response:
    """Handle the /export endpoint to convert and process annotation data.

    Returns:
        Response: JSON response indicating success or failure.
    """
    try:
        annotation_id: str = request.args.get('annotationId')
        queue_id: str = request.args.get('queueId')

        if not annotation_id or not queue_id:
            return jsonify({'success': False, 'error': 'Missing annotationId or queueId'}), 400

        # Initialize Rossum client
        client = APIClient(
            username=ROSSUM_USERNAME,
            password=ROSSUM_PASSWORD,
            base_url=ROSSUM_BASE_URL,
        )

        # Export data from Rossum
        exported_xml = b''
        async for chunk in export_annotations_to_file(
            client=client, queue_id=queue_id, export_format='xml', id=annotation_id
        ):
            exported_xml += chunk
        exported_xml = exported_xml.decode('utf-8')

        try:
            converted_xml = convert_xml(exported_xml)
            print(repr(converted_xml))
        except Exception as e:
            return jsonify({'success': False, 'error': 'Incorrect annotation schema'}), 500

        # Prepare data for Postbin
        payload = {
            'annotationId': annotation_id,
            'content': base64.b64encode(converted_xml.encode('utf-8')).decode('utf-8')
        }

        # Send POST request to Postbin
        async with aiohttp.ClientSession() as session:
            async with session.post(POSTBIN_URL, json=payload) as resp:
                if resp.status == 200 or resp.status == 201:
                    return jsonify({'success': True}), 200
                else:
                    return jsonify({'success': False, 'error': f'Failed to post to Postbin: {resp.status}'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': 'An error occurred during the export process'}), 500


if __name__ == '__main__':
app.run(host='0.0.0.0', port=5000)
