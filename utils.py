# utils.py

"""Utilidades varias para PDFimpresistem: limpieza de carpetas, parsing de páginas,
conversión de colores y otras operaciones auxiliares de procesamiento de PDF."""

from config import UPLOAD_FOLDER, OUTPUT_FOLDER
import shutil
import os
import platform


def limpiar_carpeta(carpeta):
    """
    Elimina todos los archivos y subcarpetas dentro de una carpeta.

    Args:
        carpeta (str): Ruta absoluta de la carpeta a limpiar.
    """
    for nombre in os.listdir(carpeta):
        ruta = os.path.join(carpeta, nombre)
        try:
            if os.path.isfile(ruta):
                os.remove(ruta)
            elif os.path.isdir(ruta):
                shutil.rmtree(ruta)
        except Exception as e:
            print(f'[Limpieza] Error eliminando {ruta}: {e}')


def limpiar_archivos_programada():
    """
    Limpia las carpetas /uploads y /outputs a las 7 PM hora Colombia.

    Es ejecutada automáticamente por APScheduler.
    """
    print('[Limpieza] Ejecutando limpieza programada...')
    limpiar_carpeta(UPLOAD_FOLDER)
    limpiar_carpeta(OUTPUT_FOLDER)
    print('[Limpieza] Limpieza completada.')


def eliminar_motw(filepath):
    """
    Elimina el Mark of the Web (MOTW) de un archivo en sistemas Windows.

    Windows añade un Alternate Data Stream (ADS) llamado 'Zone.Identifier'
    a los archivos descargados de Internet u otras zonas de seguridad.
    Esta marca hace que Office/el visor de PDF muestren advertencias de
    "archivo no seguro" y, desde la actualización de octubre 2025, bloquee
    la vista previa en el Explorador.

    Límite de alcance: esta función solo limpia el archivo en el servidor.
    El navegador del cliente puede volver a marcar el archivo como "de
    Internet" al descargarlo, dependiendo de la configuración de zona de
    seguridad de Windows de cada equipo. Si el problema persiste, evaluar
    agregar el dominio a la zona de Intranet local vía GPO.

    Args:
        filepath (str): Ruta absoluta del archivo a limpiar.

    Returns:
        None: La función no retorna nada. Es un no-op silencioso si el
        sistema no es Windows, el archivo no existe, no tiene ADS o el
        proceso no tiene permisos para eliminarlo.
    """
    # El MOTW es una característica exclusiva de NTFS en Windows.
    # En Linux/macOS (ej: Docker) no aplica — no-op silencioso.
    if platform.system() != 'Windows':
        return

    ads_path = filepath + ':Zone.Identifier'
    try:
        if os.path.exists(ads_path):
            os.remove(ads_path)
    except (OSError, PermissionError):
        # No tiene ADS, o el proceso no puede eliminarlo (archivo en uso,
        # permisos insuficientes). Se ignora silenciosamente.
        pass


def parsear_paginas(texto, total_paginas):
    """
    Convierte un string de páginas a una lista de índices (base 0).

    Args:
        texto (str): String con páginas (ej: '1,3-5,8').
        total_paginas (int): Total de páginas del documento.

    Returns:
        list[int]: Lista ordenada de índices base 0.

    Raises:
        ValueError: Si el formato del rango es inválido.
    """
    paginas = set()
    partes = texto.split(',')
    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue
        if '-' in parte:
            extremos = parte.split('-', 1)
            if len(extremos) != 2 or not extremos[0].strip() or not extremos[1].strip():
                raise ValueError('Formato de rango inválido.')
            inicio = int(extremos[0])
            fin = int(extremos[1])
            if inicio > fin:
                raise ValueError('El rango de páginas debe ir de menor a mayor.')
            for n in range(inicio, fin + 1):
                paginas.add(n - 1)
        else:
            paginas.add(int(parte) - 1)
    return sorted([p for p in paginas if 0 <= p < total_paginas])


def hex_a_rgb(hex_color):
    """
    Convierte un color hexadecimal a tupla RGB normalizada (0.0 - 1.0).

    Args:
        hex_color (str): Color en formato hex (ej: '#ff0000' o 'ff0000').

    Returns:
        tuple[float, float, float]: Tupla (r, g, b) con valores entre 0.0 y 1.0.
    """
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16) / 255  # int('ff', 16) = 255 / 255 = 1.0
    g = int(hex_color[2:4], 16) / 255
    b = int(hex_color[4:6], 16) / 255
    return (r, g, b)