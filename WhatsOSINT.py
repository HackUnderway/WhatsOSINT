#BY: HACK UNDERWAY

from dotenv import load_dotenv
from colorama import Fore, Style, init

from whatsosint_client import (
    CheckerError,
    ConfigError,
    WhatsOSINTClient,
    load_config,
)

# Inicializar Colorama
init(autoreset=True)

# Cargar las variables de entorno desde el archivo .env
load_dotenv()


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


# Función para consultar datos de WhatsApp usando el cliente configurado
def consultar_numero_whatsapp(client, numero_telefono):
    try:
        datos = client.check(numero_telefono)
        imprimir_json_coloreado(datos)
    except CheckerError as err:
        print(f"{Fore.RED}Error en la consulta: {err}{Style.RESET_ALL}")
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

    # Cargar y validar la configuración antes de pedir el número
    try:
        config = load_config()
    except ConfigError as err:
        print(f"{Fore.RED}Error de configuración: {err}{Style.RESET_ALL}")
        return

    numero = input("Introduce el número de teléfono (con código de país): ").strip()

    # Validar si se ingresó un número
    if not numero:
        print("Debe ingresar un número de teléfono válido.")
        return

    client = WhatsOSINTClient(config)
    # Consultar datos del número
    consultar_numero_whatsapp(client, numero)


if __name__ == "__main__":
    main()
