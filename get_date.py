from datetime import datetime, timedelta, timezone

import requests, aiohttp

headers = {
    'content-type': 'application/json+protobuf'
}


async def check_timestamp(lat, lng, start, end, radius, session):
    data = f'[["apiv3"],[[null,null,{lat},{lng}],{radius}],[[null,null,null,null,null,null,null,null,null,null,[{start},{end}]],null,null,null,null,null,null,null,[1],null,[[[2,true,2]]]],[[2,6]]]'

    async with session.post(
        'https://maps.googleapis.com/$rpc/google.internal.maps.mapsjs.v1.MapsJsInternalService/SingleImageSearch',
        headers = headers,
        data = data,
    ) as response:
        res = await response.text()
        return 'Search returned no images.' not in res


async def find_accurate_timestamp(lat, lng, date, radius, accuracy=1):
    year, month = map(int, date.split('-'))

    start_date = datetime(year, month, 1, tzinfo=timezone.utc) - timedelta(days=1)
    end_date = datetime(year, month, 1, tzinfo=timezone.utc) + timedelta(days=32)
    initial_end_date = end_date

    async with aiohttp.ClientSession() as session:
        while True:
            # Calculate the midpoint timestamp
            total_seconds = (end_date - start_date).total_seconds()
            midpoint_date = start_date + timedelta(seconds=total_seconds // 2)

            if total_seconds <= accuracy:
                # None of the time range checks worked, so failed to get timestamp
                if (initial_end_date - midpoint_date).total_seconds() <= 1:
                    raise Exception('Failed to get date')
                return int(midpoint_date.timestamp())

            midpoint_timestamp = midpoint_date.timestamp()
            if await check_timestamp(lat, lng, start_date.timestamp(), midpoint_timestamp, radius, session):
                end_date = midpoint_date
            else:
                start_date = midpoint_date

