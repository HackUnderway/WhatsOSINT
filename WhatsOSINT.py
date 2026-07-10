#BY: HACK UNDERWAY

import json
import os
from datetime import datetime
from dotenv import load_dotenv
from colorama import Fore, Style, init
from fpdf import FPDF  # Requiere fpdf2 >= 2.7.6

from whatsosint_client import (
    CheckerError,
    ConfigError,
    WhatsOSINTClient,
    load_config,
)

# Inicializar Colorama
init(autoreset=True)

# Cargar variables de entorno
load_dotenv()

# Carpeta de reportes
REPORTS_DIR = "reports"
os.makedirs(REPORTS_DIR, exist_ok=True)


# ==================== IMPRESIÓN CON COLOR ====================

def imprimir_json_coloreado(data, nivel=0):
    """Imprime JSON con colores y sangría."""
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


# ==================== EXPORTACIÓN ====================

def guardar_reporte_json(datos, numero):
    """Guarda JSON en carpeta reports/."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"reporte_{numero}_{timestamp}.json"
    ruta_completa = os.path.join(REPORTS_DIR, nombre_archivo)
    
    with open(ruta_completa, 'w', encoding='utf-8') as f:
        json.dump(datos, f, indent=4, ensure_ascii=False)
    
    print(f"{Fore.GREEN}✅ Reporte JSON guardado: {ruta_completa}{Style.RESET_ALL}")
    return ruta_completa


def generar_pdf(datos, numero):
    """Genera PDF con resumen detallado en carpeta reports/."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"reporte_{numero}_{timestamp}.pdf"
    ruta_completa = os.path.join(REPORTS_DIR, nombre_archivo)
    
    pdf = FPDF()
    pdf.add_page()
    
    # Función para sanitizar texto (latin-1)
    def safe_text(txt):
        if txt is None:
            return "N/A"
        return str(txt).encode('latin-1', errors='replace').decode('latin-1')
    
    # Título
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(200, 10, text=safe_text("Reporte de WhatsApp OSINT"), new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.ln(5)
    
    # Información General
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(200, 10, text=safe_text("Información General:"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('Helvetica', '', 12)
    
    def add_line(label, value):
        if value is not None and value != "":
            pdf.cell(50, 8, text=safe_text(f"{label}:"), border=0)
            pdf.cell(140, 8, text=safe_text(value), border=0, new_x="LMARGIN", new_y="NEXT")
    
    add_line("Número", datos.get('number', 'N/A'))
    add_line("País", datos.get('countryCode', 'N/A'))
    add_line("Teléfono", datos.get('phone', 'N/A'))
    add_line("Usuario WhatsApp", "Sí" if datos.get('isUser') else "No")
    add_line("Contacto WhatsApp", "Sí" if datos.get('isWAContact') else "No")
    add_line("Es empresa", "Sí" if datos.get('isBusiness') else "No")
    add_line("Verificado", "Sí" if datos.get('isVerified') else "No")
    add_line("Estado (about)", datos.get('about', 'N/A'))
    add_line("URL de imagen de perfil", datos.get('profilePic', 'N/A'))
    add_line("URL de imagen (cache)", datos.get('urlImage', 'N/A'))
    add_line("Fecha de consulta", datos.get('date', 'N/A'))
    
    # Perfil de negocio
    business = datos.get('businessProfile')
    if business:
        pdf.ln(5)
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(200, 10, text=safe_text("Perfil de Negocio:"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font('Helvetica', '', 12)
        add_line("  Descripción", business.get('description', 'N/A'))
        add_line("  Email", business.get('email', 'N/A'))
        website = business.get('website')
        if website and isinstance(website, list) and len(website) > 0:
            add_line("  Sitio web", website[0])
        else:
            add_line("  Sitio web", business.get('website', 'N/A'))
        add_line("  Dirección", business.get('address', 'N/A'))
        categories = business.get('categories')
        if categories and isinstance(categories, list):
            cats = [cat.get('localized_display_name', '') for cat in categories if cat.get('localized_display_name')]
            if cats:
                add_line("  Categorías", ', '.join(cats))
    
    # Análisis de imagen
    face = datos.get('faceAnalysis')
    if face:
        pdf.ln(5)
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(200, 10, text=safe_text("Análisis de Imagen:"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font('Helvetica', '', 12)
        add_line("  Descripción", face.get('description', 'N/A'))
        tags = face.get('tags', [])
        if tags:
            add_line("  Etiquetas", ', '.join(tags[:8]))
        add_line("  Modelo", face.get('model', 'N/A'))
        add_line("  Calidad de imagen", face.get('imageQuality', 'N/A'))
    
    # Historial de estados
    about_history = datos.get('aboutHistory')
    if about_history and isinstance(about_history, list) and len(about_history) > 0:
        pdf.ln(5)
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(200, 10, text=safe_text("Historial de Estados:"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font('Helvetica', '', 10)
        for item in about_history[:3]:
            date = item.get('date', '')
            about = item.get('about', '')
            pdf.cell(200, 6, text=safe_text(f"  - {date}: {about}"), new_x="LMARGIN", new_y="NEXT")
    
    # Guardar
    pdf.output(ruta_completa)
    print(f"{Fore.GREEN}✅ Reporte PDF guardado: {ruta_completa}{Style.RESET_ALL}")
    return ruta_completa


# ==================== CONSULTA ====================

def consultar_numero_whatsapp(client, numero_telefono):
    try:
        datos = client.check(numero_telefono)
        imprimir_json_coloreado(datos)
        return datos
    except CheckerError as err:
        print(f"{Fore.RED}Error en la consulta: {err}{Style.RESET_ALL}")
        return None
    except Exception as err:
        print(f"{Fore.RED}Ocurrió un error: {err}{Style.RESET_ALL}")
        return None


# ==================== MAIN ====================

def main():
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

    print(f"{Fore.YELLOW}{Style.BRIGHT}☕ Donations: https://ko-fi.com/hackunderway{Style.RESET_ALL}")
    print()

    try:
        config = load_config()
    except ConfigError as err:
        print(f"{Fore.RED}Error de configuración: {err}{Style.RESET_ALL}")
        return

    numero = input("Introduce el número de teléfono (con código de país): ").strip()
    if not numero:
        print("Debe ingresar un número de teléfono válido.")
        return

    client = WhatsOSINTClient(config)
    datos = consultar_numero_whatsapp(client, numero)

    if datos:
        print(f"\n{Fore.CYAN}📊 Generando reportes...{Style.RESET_ALL}")
        guardar_reporte_json(datos, numero)
        generar_pdf(datos, numero)
        print(f"{Fore.GREEN}✅ Reportes generados exitosamente en la carpeta '{REPORTS_DIR}'.{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
