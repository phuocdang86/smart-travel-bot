import requests

headers = {
    "X-RapidAPI-Key": "755bd08de8msh447acc8dbc9f228p1c3a81jsne431d641d721",
    "X-RapidAPI-Host": "booking-com15.p.rapidapi.com",
    "Accept": "application/json"
}

params = {
    "checkin_date": "2024-06-03",
    "checkout_date": "2024-06-05",
    "adults_number": "1",
    "search_id": "-126693",  # Rome
    "dest_type": "city",
    "order_by": "price",
    "locale": "en-gb",
    "room_number": "1",
    "units": "metric",
    "filter_by_currency": "USD"
}

response = requests.get("https://booking-com15.p.rapidapi.com/api/v1/hotels/searchHotels", headers=headers, params=params)

print(response.status_code)
print(response.text)
