#BY: HACK UNDERWAY

import os
import requests
import json
from dotenv import load_dotenv
from colorama import Fore, Style, init

# Inicializar Colorama
init(autoreset=True)

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# Clave de API y host desde el archivo .env
api_key = os.getenv('RAPIDAPI_KEY')
api_host = os.getenv('RAPIDAPI_HOST')

# Función para imprimir el JSON con formato y colores
def imprimir_json_coloreado(data, nivel=0):
    indent = "    " * nivel
    if isinstance(data, dict):
        for key, value in data.items():
            print(f"{indent}{Fore.CYAN}{key}{Style.RESET_ALL}: ", end="")
            imprimir_json_coloreado(value, nivel + 1)
    elif isinstance(data, list):
        for item in data:
            imprimir_json_coloreado(item, nivel)
    else:
        print(f"{Fore.YELLOW}{data}{Style.RESET_ALL}")

# Función para consultar datos de WhatsApp
def consultar_numero_whatsapp(numero_telefono):
    url = f"https://{api_host}/number/{numero_telefono}"
    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": api_host
    }
    
    try:
        # Realizar la solicitud GET a la API
        response = requests.get(url, headers=headers)
        
        # Verificar si la solicitud fue exitosa
        response.raise_for_status()
        
        # Obtener la respuesta en formato JSON
        datos = response.json()
        
        # Imprimir el JSON formateado y coloreado
        imprimir_json_coloreado(datos)
    
    except requests.exceptions.HTTPError as http_err:
        print(f"{Fore.RED}Error HTTP: {http_err}{Style.RESET_ALL}")
    except requests.exceptions.RequestException as req_err:
        print(f"{Fore.RED}Error en la solicitud: {req_err}{Style.RESET_ALL}")
    except json.JSONDecodeError:
        print(f"{Fore.RED}Error al procesar la respuesta JSON.{Style.RESET_ALL}")
    except Exception as err:
        print(f"{Fore.RED}Ocurrió un error: {err}{Style.RESET_ALL}")

def main():
    # Banner verde
    print(Fore.GREEN + """
     __i
    |---|    
    |[_]|    
    |:::|    
    |:::|    
    `\\   \\   
      \\_=_\\ 
    Consulta de datos de número de WhatsApp
    """ + Style.RESET_ALL)

    numero = input("Introduce el número de teléfono (con código de país): ")
    
    # Validar si se ingresó un número
    if not numero.strip():
        print("Debe ingresar un número de teléfono válido.")
        return
    
    # Consultar datos del número
    consultar_numero_whatsapp(numero)

if __name__ == "__main__":
    main()
