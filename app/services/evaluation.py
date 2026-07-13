from app.models.partido import Partido
from app.models.prediccion import Prediccion


def evaluar_prediccion(partido: Partido) -> bool | None:
    """Marca la prediccion como acierto/fallo comparando con el resultado real.

    Devuelve el valor de acierto o None si aun no hay resultado o prediccion.
    """
    prediccion: Prediccion | None = partido.prediccion
    resultado = partido.resultado
    if prediccion is None or resultado is None:
        return None

    acierto = prediccion.pronostico == resultado.ganador
    prediccion.acierto = acierto
    return acierto
