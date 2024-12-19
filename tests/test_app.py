import os
import pytest
import asyncio
import base64
from unittest.mock import patch, AsyncMock
from app import app

# Load .env file
from dotenv import load_dotenv
load_dotenv()


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.mark.asyncio
@patch('app.APIClient')
@patch('aiohttp.ClientSession.post')
async def test_export_success(mock_postbin_post, mock_rossum_client, client):
    # Mock Rossum SDK export response
    mock_client_instance = mock_rossum_client.return_value

    # Create XML content
    xml_content = '''<?xml version="1.0" encoding="utf-8"?>
    <export><results><annotation url="https://elis.rossum.ai/api/v1/annotations/2451971"><status>exported</status><arrived_at>2020-07-15T06:43:23.028579Z</arrived_at><exported_at>2021-03-08T06:18:30.682878Z</exported_at><document url="https://elis.rossum.ai/api/v1/documents/2453838"><file_name>EU Marketing Invoice (Norway).pdf</file_name><file>https://elis.rossum.ai/api/v1/documents/2453838/content</file></document><modifier url="https://elis.rossum.ai/api/v1/users/13564"><username>test_578459@elis.rossum.ai</username></modifier><schema url="https://elis.rossum.ai/api/v1/schemas/176091"></schema><metadata></metadata><content><section schema_id="invoice_info_section"><datapoint rir_confidence="0.9771588350454424" schema_id="invoice_id" type="string">143453775</datapoint><datapoint rir_confidence="0.9633343080893669" schema_id="date_issue" type="date">2019-03-01</datapoint><datapoint rir_confidence="0.9276531531670439" schema_id="date_due" type="date">2019-03-31</datapoint><datapoint rir_confidence="0.8970364740042044" schema_id="iban" type="string">NO6513425245230</datapoint></section><section schema_id="amounts_section"><datapoint rir_confidence="0.9252583542257525" schema_id="amount_total" type="number">12978.81</datapoint><datapoint rir_confidence="0.960040642328732" schema_id="amount_total_tax" type="number">2595.76</datapoint><datapoint schema_id="amount_total_base" type="number"></datapoint><datapoint rir_confidence="0.6738755702972412" schema_id="currency" type="enum">nok</datapoint><multivalue schema_id="vat_details"></multivalue></section><section schema_id="vendor_section"><datapoint rir_confidence="0.5393862589945768" schema_id="sender_name" type="string">InfoNet Workshop</datapoint><datapoint rir_confidence="0.9061709945951922" schema_id="sender_address" type="string">2423 KONGSVINGER
    Norway</datapoint><datapoint schema_id="sender_ic" type="string"></datapoint><datapoint schema_id="sender_dic" type="string"></datapoint><datapoint schema_id="recipient_name" type="string"></datapoint><datapoint rir_confidence="0.93205490037382" schema_id="recipient_address" type="string"></datapoint><datapoint schema_id="recipient_ic" type="string"></datapoint><datapoint schema_id="recipient_dic" type="string"></datapoint></section><section schema_id="others_section"></section><section schema_id="line_items_section"><multivalue schema_id="line_items"><tuple schema_id="line_item"><datapoint schema_id="item_description" type="string">HPi Battery 4C 40WHr 2 BAH LI LA098241</datapoint><datapoint schema_id="item_quantity" type="number">3</datapoint><datapoint schema_id="item_amount_base" type="number"></datapoint><datapoint schema_id="item_rate" type="number"></datapoint><datapoint schema_id="item_amount" type="number">645.53</datapoint><datapoint schema_id="item_amount_total_base" type="number"></datapoint><datapoint schema_id="item_amount_total" type="number">1936.59</datapoint></tuple><tuple schema_id="line_item"><datapoint schema_id="item_description" type="string">HP 11.6-inch HD WLED UWVA touchscreen display ass</datapoint><datapoint schema_id="item_quantity" type="number">4</datapoint><datapoint schema_id="item_amount_base" type="number"></datapoint><datapoint schema_id="item_rate" type="number"></datapoint><datapoint schema_id="item_amount" type="number">2077.14</datapoint><datapoint schema_id="item_amount_total_base" type="number"></datapoint><datapoint schema_id="item_amount_total" type="number">8308.56</datapoint></tuple><tuple schema_id="line_item"><datapoint schema_id="item_description" type="string">fre-ghti</datapoint><datapoint schema_id="item_quantity" type="number">1</datapoint><datapoint schema_id="item_amount_base" type="number"></datapoint><datapoint schema_id="item_rate" type="number"></datapoint><datapoint schema_id="item_amount" type="number">137.90</datapoint><datapoint schema_id="item_amount_total_base" type="number"></datapoint><datapoint schema_id="item_amount_total" type="number">137.90</datapoint></tuple></multivalue></section></content><automated>false</automated><modified_at>2021-03-08T06:18:20.940441Z</modified_at><assigned_at>2021-03-08T06:17:17.554572Z</assigned_at></annotation></results><pagination><next></next><previous></previous><total>1</total><total_pages>1</total_pages></pagination></export>'''

    # Create an async generator that yields XML content as bytes
    async def mock_export(*args, **kwargs):
        yield xml_content.encode('utf-8')

    # Set up mock to return async generator
    mock_client_instance.export = mock_export

    # Mock Postbin response
    mock_postbin_response = AsyncMock()
    mock_postbin_response.status = 200
    mock_postbin_post.return_value.__aenter__.return_value = mock_postbin_response

    # Prepare test data
    test_data = {
        "annotationId": "2451971",
        "queueId": "12345"
    }

    # Needed for Flask asyncio support (there are asyncio loop conflicts otherwise)
    def sync_test():
        # Create auth credentials string
        credentials = base64.b64encode(
            f"{os.getenv('APP_USERNAME')}:{os.getenv('APP_PASSWORD')}".encode()
        ).decode('utf-8')

        # Make request with Basic Auth
        response = client.get(
            '/export',
            query_string=test_data,
            headers={'Authorization': f'Basic {credentials}'}
        )

        # Check response
        assert response.status_code == 200
        assert response.json == {'success': True}

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, sync_test)
