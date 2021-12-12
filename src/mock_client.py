import argparse

import boto3
from boto3.dynamodb.conditions import Key, And

def main(table_name, location, date):
    # boto3 is the AWS SDK library for Python.
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.Table(table_name)

    condition = Key('location').eq(location)
    if date is not None:
        condition = (condition & Key('eventinfo').begins_with(date))

    resp = table.query(KeyConditionExpression=condition)

    print(f"weather stats for {location} ({date if date is not None else 'all'}):")
    for item in resp['Items']:
        if table_name == 'data650-Precipitation':
            value = f"{int(item['value'])} mm"
        else:
            value = f"{int(item['value']) / 10} deg C"
        print(f"({item['date']}) - {item['datatype']}: {value}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="retrieves records from dynamodb")
    parser.add_argument("table", help="table to query")
    parser.add_argument("location", help="location of measurements to collect")
    parser.add_argument("--date", default=None, help="date for measurement")
    args = parser.parse_args()

    main(args.table, args.location, args.date)
