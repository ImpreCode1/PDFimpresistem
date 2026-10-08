# pdf2docx_compat.py — Parche de compatibilidad para pdf2docx==0.5.12

"""Corrige la pérdida de imágenes dentro de tablas al convertir PDF a Word.

Bug de pdf2docx 0.5.12
-----------------------
Al asignar el contenido a las celdas de una tabla, ``Layout._assign_block``
recorta cada línea con ``Line.intersects()``. Ese recorte invoca a
``ImageSpan.intersects()``, que solo conserva la imagen si al menos el 75%
de su área (``constants.FACTOR_MAJOR``) cae dentro de UNA sola celda. Si
una imagen queda repartida entre varias celdas (p. ej. una foto que cruza
bordes horizontales de una tabla), ninguna celda llega a ese umbral, cada
recorte devuelve un ``ImageSpan`` vacío y la imagen se descarta por
completo: el Word final sale sin esa imagen.

Cómo funciona el parche
-----------------------
``TableBlock.assign_blocks`` separa las líneas que contienen una imagen
real y las coloca directamente en la celda con la que mayor área solapan,
preservando la línea completa (sin recortarla). El resto de elementos
(texto y sub-tablas) se procesa con el método original, de modo que los
documentos sin imágenes se comportan exactamente igual que antes.

La posición visual no cambia: pdf2docx 0.5.12 dibuja las imágenes como
flotantes con posición absoluta de página (``add_image`` ->
``positionH/V relativeFrom="page"``), así que la imagen aparece exactamente
donde estaba en el PDF sin desplazar el contenido de la celda.

Multiprocesamiento
------------------
Con ``multi_processing=True`` (Linux, documentos de 30+ páginas) el
análisis de páginas ocurre en procesos hijos. En Python >= 3.14 el método
de arranque por defecto en Linux es ``forkserver``: los hijos se crean con
``fork`` a partir de un proceso intermedio que importa los módulos de una
lista de precarga, no el código de la aplicación. Por eso se registra este
módulo en esa lista para que el parche también esté activo en los hijos.
En Python <= 3.13 (arranque ``fork``) los hijos heredan el parche
directamente del proceso padre.

Uso:
    import pdf2docx_compat  # basta con importarlo una vez, antes de convertir
"""

import logging
import platform

import multiprocessing

from pdf2docx.image.ImageSpan import ImageSpan
from pdf2docx.table.TableBlock import TableBlock

logger = logging.getLogger(__name__)


def _es_linea_con_imagen(bloque):
    """True si el bloque es una línea que contiene una imagen real.

    Los ``ImageSpan`` vacíos (creados por ``ImageSpan.intersects`` cuando la
    imagen no llega al umbral de la celda) no cuentan: no llevan bytes.
    """
    image_spans = getattr(bloque, 'image_spans', None)
    if image_spans is None:
        return False
    return any(span.image for span in image_spans)


def _area_solape(a, b):
    """Área de intersección entre dos bboxes (tuplas o fitz.Rect)."""
    x0 = max(float(a[0]), float(b[0]))
    y0 = max(float(a[1]), float(b[1]))
    x1 = min(float(a[2]), float(b[2]))
    y1 = min(float(a[3]), float(b[3]))
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return (x1 - x0) * (y1 - y0)


if not getattr(TableBlock, '_pdf2docx_compat_patch', False):
    _assign_blocks_original = TableBlock.assign_blocks

    def _assign_blocks_con_imagenes(self, blocks):
        """Versión parcheada de ``TableBlock.assign_blocks`` (ver módulo).

        Las líneas con imagen van a la celda de mayor solape conservándose
        completas; el resto se delega sin cambios al método original.
        """
        lineas_imagen = [b for b in blocks if _es_linea_con_imagen(b)]

        # Sin imágenes en juego: comportamiento idéntico al original.
        if not lineas_imagen:
            return _assign_blocks_original(self, blocks)

        resto = [b for b in blocks if not _es_linea_con_imagen(b)]
        _assign_blocks_original(self, resto)

        celdas = [
            celda
            for fila in self._rows
            for celda in fila
            if celda  # ignora celdas combinadas (bbox vacío), como el original
        ]
        for linea in lineas_imagen:
            if not celdas:
                # Tabla sin celdas utilizables: no hay dónde colocarla; se
                # descarta igual que haría el método original.
                logger.warning(
                    '[pdf2docx_compat] Tabla %s sin celdas: imagen %s '
                    'descartada por el original',
                    [round(v, 1) for v in self.bbox],
                    [round(v, 1) for v in linea.bbox],
                )
                continue

            # Celda con la que más área solapa; los empates se resuelven a
            # favor de la primera celda (orden de lectura).
            celda = max(
                celdas,
                key=lambda c: _area_solape(c.bbox, linea.bbox),
            )
            celda.blocks.append(linea)
            logger.info(
                '[pdf2docx_compat] Imagen conservada en celda %s '
                '(solape %d pt²): %s',
                [round(v, 1) for v in celda.bbox],
                _area_solape(celda.bbox, linea.bbox),
                [round(v, 1) for v in linea.bbox],
            )

    _assign_blocks_con_imagenes.__doc__ = (
        'TableBlock.assign_blocks parcheado para no perder imágenes '
        '(ver pdf2docx_compat).'
    )

    TableBlock.assign_blocks = _assign_blocks_con_imagenes
    TableBlock._pdf2docx_compat_patch = True

# ----------------------------------------------------------------------------
# Precarga del forkserver (Linux): los hijos de pdf2docx se crean con fork a
# partir de un proceso intermedio que solo importa los módulos de esta lista.
# Al registrar este módulo aquí, el parche anterior también se aplica dentro
# de los procesos que analizan las páginas con multiprocesamiento. Debe
# hacerse antes de la primera conversión con multi_processing (el forkserver
# se lanza entonces y ya no admite cambios en la lista).
# ----------------------------------------------------------------------------
if platform.system() == 'Linux':
    try:
        multiprocessing.get_context('forkserver').set_forkserver_preload([
            '__main__',           # comportamiento por defecto de Python
            'pdf2docx_compat',    # este parche
        ])
    except Exception as exc:  # pragma: no cover — nunca debe romper la app
        logger.warning(
            '[pdf2docx_compat] No se pudo registrar la precarga del '
            'forkserver: %s', exc,
        )
