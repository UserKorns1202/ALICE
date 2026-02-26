import pyshark
import requests
import threading
import time
import pygame

global monitoring_flag
monitoring_flag = True

# Function to get IP geolocation using ipinfo.io
def get_ip_geolocation(ip):
    try:
        response = requests.get(f"http://ipinfo.io/{ip}/json")
        data = response.json()
        # Safely get the city, region, and country with defaults if not present
        city = data.get('city', 'Unknown City')
        region = data.get('region', 'Unknown Region')
        country = data.get('country', 'Unknown Country')
        location = f"{city}, {region}, {country}"
        return location
    except Exception as e:
        print(f"Error fetching geolocation: {e}")
        return "Unknown Location"

# Function to continuously monitor network traffic
def monitor_network():
    global monitoring_flag
    while True:
        try:
            # Capture packets on interface 'Wi-Fi'
            capture = pyshark.LiveCapture(interface='Wi-Fi')

            # Sniff 10 packets
            for packet in capture.sniff_continuously(packet_count=10):
                try:
                    # Extract available layers information
                    layers = packet.layers

                    # Get the highest layer to represent the payload
                    payload = packet.highest_layer

                    # Initialize the location, source, and destination IPs
                    location = "N/A"
                    source_ip = "N/A"
                    destination_ip = "N/A"

                    # Initialize variables for extracted information
                    urls = []
                    parameters = {}
                    headers = {}
                    file_types = set()

                    # Attempt to retrieve IP information from any available layer
                    for layer in layers:
                        if hasattr(layer, 'src'):
                            source_ip = layer.src
                        if hasattr(layer, 'dst'):
                            destination_ip = layer.dst

                    # Get geolocation of the source IP (replace with actual logic if needed)
                    if source_ip != "N/A":
                        location = get_ip_geolocation(source_ip)

                    # Extract information based on protocol (e.g., HTTP)
                    if packet.transport_layer == 'TCP':
                        # Check if the HTTP layer exists
                        if hasattr(packet, 'http'):
                            # Extract HTTP information
                            for field in packet.http._all_fields:
                                if field.startswith('http.'):
                                    key = field.split('.')[-1]
                                    try:
                                        value = packet.http[field]
                                    except:
                                        value = "N/A"
                                    # Handle different HTTP fields as needed
                                    if key == 'request_uri' or key == 'request_full_uri':
                                        urls.append(value)
                                    elif key == 'request_method':
                                        parameters['Method'] = value
                                    elif key == 'response_code':
                                        parameters['Response Code'] = value
                                    elif key == 'user_agent':
                                        headers['User-Agent'] = value
                                    elif key == 'cookie':
                                        headers['Cookie'] = value
                        else:
                            # Skip processing further if HTTP layer is not found
                            continue

                    # Print the distilled information
                    print(f"Origin Location: {location}")
                    print(f"Source IP: {source_ip}")
                    print(f"Destination IP: {destination_ip}")
                    print(f"Payload: {payload}")
                    print(f"URLs: {urls}")
                    print(f"Parameters: {parameters}")
                    print(f"Headers: {headers}")
                    print(f"File Types: {file_types}\n")

                except AttributeError as e:
                    # Handle packets that do not have the expected attributes
                    print(f"Packet does not have expected attributes: {e}")
                    continue

        except KeyboardInterrupt:
            print("Monitoring stopped by user.")
            break
        except Exception as e:
            print(f"Error in network monitoring thread: {e}")

def start_monitoring():
    global monitoring_flag
    # Start a thread for network monitoring
    monitoring_flag = True
    monitor_network()
    print("Monitoring started.")


# Example usage
start_monitoring()
