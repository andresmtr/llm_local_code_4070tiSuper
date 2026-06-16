# Use only the 'requests' library for API calls.
import requests
from django.conf import settings
from django.core.exceptions import RequestException

def fetch_beneficiaries_data(api_endpoint: str):
    """
    Fetches beneficiary data from the Socrata API endpoint.
    
    Args:
        api_endpoint: The base URL of the Socrata API.

    Returns:
        dict: A dictionary containing the list of records or None if fetching fails.
"""
    print(f"Attempting to fetch data from: {api_endpoint}")
    
    try:
        # Socrata API often requires the inclusion of 'fields' to guarantee structure,
        # but for simplicity, we'll rely on the default query parameters.
        response = requests.get(api_endpoint, timeout=15)
        response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
        
        data = response.json()
        # The typical Socrata response structure contains the records under a list key
        if 'records' in data and data['records']:
            return data['records']
        elif isinstance(data, list):
            # Some APIs might return a list directly
            return data
        else:
            print("API response structure unexpected. Returning empty data.")
            return {'beneficiarios': []}

    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error fetching data: {e}")
        # Re-raise to let the view catch it as a known operational error
        raise RequestException(f"Failed to fetch data due to HTTP error: {e}")
    except requests.exceptions.ConnectionError as e:
        print(f"Connection Error: {e}")
        raise RequestException(f"Failed to connect to the API endpoint.")
    except requests.exceptions.Timeout as e:
        print(f"Timeout Error: {e}")
        raise RequestException(f"The API request timed out.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise RequestException(f"An unexpected error occurred during data fetching.")