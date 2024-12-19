# Python Web application for XML conversion

Simple Python web application written in Flask framework with one endpoint
/export that will convert data from the XML downloaded from Rossum
to a XML in another format.


## Usage

1. Create `.env` file in app directory with content like this:
    ```
    APP_USERNAME=app username
    APP_PASSWORD=app password
    ROSSUM_USERNAME=your Rossum username
    ROSSUM_PASSWORD=your Rossum password
    ROSSUM_BASE_URL=https://mktest.rossum.app/api/v1
    POSTBIN_URL=https://www.postb.in/1734593088234-6799550740979
    ```

    Obtain new POSTBIN_URL on https://www.postb.in

2. Build Docker image:
    ```
    docker build -t rossum-app .
    ```

3. Run app in Docker container:
    ```
    docker run -d -p 5000:5000 --env-file .env rossum-app
    ```

4. Access web app API like this:
    ```
    http://127.0.0.1:5000/export?queueId=1500938&annotationId=5692640
    ```

5. Check prepared Postbin page to see the request


## Tests

For running tests, create Python virtual environment, install requirements and
run `pytest`:

```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pytest
```
