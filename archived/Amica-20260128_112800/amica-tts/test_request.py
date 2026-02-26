import requests

URL = "http://127.0.0.1:5002/v1/audio/speech"

payload = {"input": "Hello Amica - test TTS from local service"}

r = requests.post(URL, json=payload)
if r.status_code == 200:
    with open("sample_amica.wav", "wb") as f:
        f.write(r.content)
    print("WAV saved to sample_amica.wav")
else:
    print("Error", r.status_code, r.text)
