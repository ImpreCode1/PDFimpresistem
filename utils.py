# utils.py

from config import UPLOAD_FOLDER, OUTPUT_FOLDER
import shutil
import os


def limpiar_carpeta(carpeta):
    """
    Elimina todos los archivos y subcarpetas dentro de una carpeta
    sin borrar la carpeta misma.

    Si un archivo está en uso y no puede eliminarse, registra el error
    en consola y continúa con el siguiente archivo sin interrumpir el proceso.

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
    Tarea programada que limpia /uploads y /outputs a las 7 PM hora Colombia.
    Es ejecutada automáticamente por APScheduler según el CronTrigger configurado.
    """
    print('[Limpieza] Ejecutando limpieza programada...')
    limpiar_carpeta(UPLOAD_FOLDER)
    limpiar_carpeta(OUTPUT_FOLDER)
    print('[Limpieza] Limpieza completada.')


def parsear_paginas(texto, total_paginas):
    """
    Convierte un string de páginas a una lista de índices base 0.

    Acepta formatos como:
        - Páginas individuales: "1,3,5"
        - Rangos: "2-6"
        - Combinaciones: "1,3-5,8"

    Usa set() internamente para eliminar duplicados automáticamente.
    Filtra silenciosamente las páginas fuera del rango del documento.

    Args:
        texto (str): String con páginas escritas por el usuario.
        total_paginas (int): Total de páginas del documento.

    Returns:
        list[int]: Lista ordenada de índices base 0.

    Raises:
        ValueError: Si el formato de un rango es inválido (ej: "5-3").
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
    Convierte un color hexadecimal HTML a una tupla RGB normalizada (0.0 - 1.0).

    PyMuPDF requiere colores en formato RGB con valores entre 0 y 1,
    mientras que los inputs de tipo 'color' en HTML retornan hex como '#ff0000'.

    Ejemplo:
        hex_a_rgb('#ff0000') -> (1.0, 0.0, 0.0)  # rojo
        hex_a_rgb('#000000') -> (0.0, 0.0, 0.0)  # negro

    Args:
        hex_color (str): Color en formato hexadecimal, ej: '#ff0000' o 'ff0000'.

    Returns:
        tuple[float, float, float]: Tupla (r, g, b) con valores entre 0.0 y 1.0.
    """
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16) / 255  # int('ff', 16) = 255 / 255 = 1.0
    g = int(hex_color[2:4], 16) / 255
    b = int(hex_color[4:6], 16) / 255
    return (r, g, b)