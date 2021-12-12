"""
Producer module that downloads weather data from NOAA REST API.
"""
import argparse
import json
import time

import boto3
import requests

# NOAA REST endpoing that we want to access
REST_ENDPOINT = "https://www.ncdc.noaa.gov/cdo-web/api/v2/data"

# Location ID in the data set representing Maryland
MD_LOCATION_ID = "FIPS:24"

# Data set ID within the NOAA repositories
DATASET_ID = "GHCND"

# Location data
STATION_DATA_ENDPOINT = "https://www.ncdc.noaa.gov/cdo-web/api/v2/stations"

# Maximum number of records to write to a kinesis stream
MAX_RECORDS = 500

# Data fields that we are going to collect
#   SNOW - amount of snowfall (mm)
#   PRCP - amount of rainfall (mm)
#   TMIN - minimum temp (tenths of degree Celsius)
#   TMAX - maximum temp (tenths of degree Celsius)
DATA_TYPES = ["SNOW", "PRCP", "TMIN", "TMAX"]

class NoaaServer:
    """
    Defines interactions with NOAA REST API endpoints.
    """

    def __init__(self, api_token, rest_endpoint=REST_ENDPOINT):
        self._api_token = api_token
        self._rest_endpoint = rest_endpoint

    def _request_weather(self, start_date, end_date, offset=0, limit=500):
        """
        Requests data from the NOAA REST API.
        """
        headers = {
            "token": self.api_token
        }
        payload = {
            "datasetid": DATASET_ID,
            "datatypeid": ",".join(DATA_TYPES),
            "locationid": MD_LOCATION_ID,
            "startdate": start_date,
            "enddate": end_date,
            "offset": offset,
            "limit": limit
        }
        result = requests.get(REST_ENDPOINT, params=payload, headers=headers).json()

        return result["metadata"]["resultset"], result["results"]

    def _request_locations(self, offset=0, limit=500):
        """Requests location information from the NOAA REST API

        Args:
            station (str): identifier of the station
        """
        headers = {
            "token": self.api_token
        }
        payload = {
            "locationid": MD_LOCATION_ID,
            "offset": offset,
            "limit": limit
        }

        result = requests.get(STATION_DATA_ENDPOINT, headers=headers, params=payload).json()

        return result["metadata"]["resultset"], result["results"]

    def request_all_data(self, request_func):
        """
        Generator that yields all relevant data from a remote server
        """
        next_offset = 0
        recvd_all = False

        while not recvd_all:
            print(f"requesting data at offset {next_offset}")
            metadata, results = request_func(next_offset)
            yield from results
            next_offset = metadata["offset"] + metadata["limit"]
            recvd_all = next_offset > metadata["count"]

            print("sleeping for 1 second to throttle api query rate")
            time.sleep(1)

    def request_all_weather(self, start_date: str, end_date: str):
        return self.request_all_data(lambda offset: self._request_weather(start_date, end_date, offset=offset))

    def request_all_locations(self):
        result = self.request_all_data(lambda offset: self._request_locations(offset=offset))
        return {r["id"]: r["name"] for r in result}

    @property
    def api_token(self):
        """
        Property representing API token used to authenticate with NOAA REST API
        """
        return self._api_token


def main(api_token, start_date, end_date):
    """
    Main entrypoint for module.
    """
    server = NoaaServer(api_token)

    print("downloading location data")
    locations = server.request_all_locations()

    print(f"downloading weather data from {start_date} to {end_date}")
    weather_data = server.request_all_weather(start_date, end_date)

    ret = []
    for d in weather_data:
        d["location"] = locations.get(d["station"], "UNKNOWN LOCATION")
        ret.append(d)

    return ret

def lambda_handler(event, context):
    client = boto3.client("kinesis")
    api_token = event["api_token"]
    start_date = event["start_date"]
    end_date = event["end_date"]
    weather_data = main(api_token, start_date, end_date)

    records = []
    n = 0
    for d in weather_data:
        records.append({
            "Data": bytes(json.dumps(d), encoding="utf-8"),
            "PartitionKey": "1"
        })
        if len(records) == MAX_RECORDS:
            n += MAX_RECORDS
            print(f"flushing {MAX_RECORDS} to kinesis, seen {n} total")
            client.put_records(StreamName="WeatherStream", Records=records)
            records = []

    if len(records) > 0:
        print(f"flushing remaining {len(records)} records, seen {n + len(records)}")
        client.put_records(StreamName="WeatherStream", Records=records)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Producer that downloads weather data from NOAA REST API")
    parser.add_argument("api_token", help="Token used to access NOAA REST API")
    parser.add_argument("--start-date", default="2021-10-01", help="Start date for data collection")
    parser.add_argument("--end-date", default="2021-10-31", help="End date for data collection")
    args = parser.parse_args()

    ret = main(args.api_token, args.start_date, args.end_date)
    for entry in ret:
        print(json.dumps(entry))
