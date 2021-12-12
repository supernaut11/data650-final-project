"""
Module that handles requests to put weather data in central repository
"""
from base64 import b64decode
import json

import boto3
from boto3.dynamodb.conditions import Key

PRECIPITATION_TABLE = "data650-Precipitation"
TEMPERATURE_TABLE = "data650-Temperature"

PRECIPITATION_TYPES = {"SNOW", "PRCP"}
TEMPERATURE_TYPES = {"TMIN", "TMAX"}

MAX_CONSUMER_RECORDS = 500

class DynamoContext:
    """
    Represents a DynamoDB server context for AWS
    """

    def __init__(self, name, region_name="us-east-1"):
        """
        Constructor for DynamoContext object

        Args:
            name (str): name of the AWS resources
            region_name (str, optional): AWS region hosting the DynamoDB instance. Defaults to
                                        "us-east-1".
        """
        self._dynamo = boto3.resource(name, region_name)

    def put(self, table_name, items):
        """
        Puts a list of items into a table

        Args:
            table_name (str): name of the table that will receive items
            items (list): list of records to add to the table
        """
        table = self._dynamo.Table(table_name)
        with table.batch_writer() as batch:
            n = 0
            for item in items:
                batch.put_item(Item=item)
                n += 1
            print(f"wrote batch of size {n} to dynamo")

    def get(self, table_name, key_expr):
        """
        Gets a list of items from a table matching the key expression

        Args:
            table_name (str): name of table to query
            key_expr (Key): key expression used to find relevant records

        Yields:
            [type]: [description]
        """
        yield from self._dynamo.Table(table_name).query(KeyConditionExpression=key_expr)


class WeatherGetter:
    """
    Object that can get weather information from a dynamodb context
    """
    def __init__(self, ctxt):
        self._ctxt = ctxt

    def _get_helper(self, table, station):
        """Helper function for getting weather measurements for a specific station

        Args:
            table (str): name of table to query for data
            station (str): name of station

        Returns:
            generator: Generator object that yields weather records for the station
        """
        key_expr = Key("Station").eq(station)
        return self._ctxt.get(table, key_expr)

    def get_precipitation(self, station):
        """Gets precipitation and snow data for a specified station

        Args:
            station (str): name of station to collect data from

        Returns:
            generator: Generator object that yields precipitation records for the station
        """
        return self._get_helper(PRECIPITATION_TABLE, station)

    def get_temperature(self, station):
        """Gets temperature data for a specified station

        Args:
            station (str): name of station to collect data from

        Returns:
            generator: Generator object that yields temperature records for the station
        """
        return self._get_helper(TEMPERATURE_TABLE, station)


class WeatherPutter:
    """
    Object that can put weather data into a dynamodb context
    """
    def __init__(self, ctxt):
        self._ctxt = ctxt

    def _put_helper(self, table, items):
        """Helper for putting weather data items into a dynamodb table

        Args:
            table (str): name of table to insert into
            items (list): list of weather record items to add to the table
        """
        self._ctxt.put(table, items)

    def put_precipitation(self, items):
        """Puts precipitation data into a dynamodb table

        Args:
            items (list): list of precipitation record items to add to the database
        """
        self._put_helper(PRECIPITATION_TABLE, items)

    def put_temperature(self, items):
        """Puts temperature data into a dynamodb table

        Args:
            items (list): list of temperature record items to add to the database
        """
        self._put_helper(TEMPERATURE_TABLE, items)

def _record_helper(item):
    return {
        "location": item["location"],
        "eventinfo": "#".join((item["date"], item["datatype"], item["station"])),
        "date": item["date"],
        "datatype": item["datatype"],
        "station": item["station"],
        "value": item["value"]
    }

def build_records(items):
    precip = []
    temps = []
    for item in items:
        t = item["datatype"]
        if t in PRECIPITATION_TYPES:
            precip.append(_record_helper(item))
        elif t in TEMPERATURE_TYPES:
            temps.append(_record_helper(item))
        else:
            print(f"WARN: skipping unsupported datatype - {t}")

    return precip, temps

def lambda_handler(event, context):
    """AWS Lambda handler function that gets invoked by Kinesis data stream

    Args:
        event (): event data provided by Kinesis data stream
        context (): context data provided by Kinesis data stream
    """
    putter = WeatherPutter(DynamoContext("dynamodb"))
    items = map(lambda x: json.loads(b64decode(x["kinesis"]["data"])), event["Records"])

    precip, temps = build_records(items)

    putter.put_precipitation(precip)
    putter.put_temperature(temps)
