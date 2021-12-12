import argparse
from datetime import datetime, timedelta
import json
import time

import boto3

DOWNLOAD_COOLDOWN_SECONDS = 60

def build_payload(api_token, start_date, end_date):
    raw_payload = {
        "api_token": api_token,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d")
    }

    return bytes(json.dumps(raw_payload), encoding="utf-8")

def trigger_loop(api_token, start_date, end_date, cooldown):
    cur_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.strptime(end_date, "%Y-%m-%d")
    one_day_delta = timedelta(days=1)

    client = boto3.client("lambda")

    while cur_date <= end_date:
        payload = build_payload(api_token, cur_date, cur_date)
        print(f"invoking lambda -> {payload}")
        client.invoke(FunctionName="producer-lambda", Payload=payload)
        print(f"sleeping for {cooldown} seconds")
        time.sleep(cooldown)
        cur_date += one_day_delta

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Triggers Kinesis producer for downloading weather data")
    parser.add_argument("token", help="NOAA API token used to access weather data")
    parser.add_argument("start", help="start date in format YYYY-MM-DD")
    parser.add_argument("end", help="end date in format YYYY-MM-DD")
    parser.add_argument("--cooldown", type=int, default=DOWNLOAD_COOLDOWN_SECONDS,
                        help="trigger cooldown (default %(default)s seconds)")
    args = parser.parse_args()

    trigger_loop(args.token, args.start, args.end, args.cooldown)
