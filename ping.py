import requests
import time
import random

url = "https://test-1-wkh6.onrender.com/"

while True:
    try:
        response = requests.get(url)
        if response.status_code == 200:
            print("Serveur ping réussi !")
        else:
            print(f"Serveur ping échoué, code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Erreur de connexion : {e}")

    # Pause aléatoire entre 10 et 14 minutes
    sleep_time = 60 * random.randint(10, 14)
    time.sleep(sleep_time)
