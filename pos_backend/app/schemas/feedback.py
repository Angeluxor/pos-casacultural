from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

TipoFeedback = Literal["Bug", "Idea", "Duda", "Otro"]
EstadoFeedback = Literal["Nuevo", "En revisión", "Resuelto", "Descartado"]
PrioridadFeedback = Literal["Baja", "Media", "Alta"]
MimeCaptura = Literal["image/png", "image/jpeg", "image/webp"]


class FeedbackCreate(BaseModel):
    tipo: TipoFeedback
    comentario: str = Field(min_length=3, max_length=4000)
    contexto: Dict[str, Any] = Field(default_factory=dict)
    captura_base64: Optional[str] = Field(default=None, max_length=3_000_000)
    captura_mime: Optional[MimeCaptura] = None
    captura_nombre: Optional[str] = Field(default=None, max_length=120)

    @field_validator("comentario")
    @classmethod
    def limpiar_comentario(cls, valor: str) -> str:
        limpio = (valor or "").strip()
        if len(limpio) < 3:
            raise ValueError("Cuéntanos un poco más (mínimo 3 caracteres).")
        return limpio

    @field_validator("captura_nombre")
    @classmethod
    def limpiar_nombre_captura(cls, valor: Optional[str]) -> Optional[str]:
        if valor is None:
            return None
        limpio = valor.strip()
        return limpio or None

    @model_validator(mode="after")
    def validar_captura_completa(self):
        if bool(self.captura_base64) != bool(self.captura_mime):
            raise ValueError(
                "La captura debe incluir la imagen y su tipo MIME al mismo tiempo."
            )
        return self


class FeedbackUpdate(BaseModel):
    estado: Optional[EstadoFeedback] = None
    prioridad: Optional[PrioridadFeedback] = None
    etiquetas: Optional[List[str]] = None
    notas_internas: Optional[str] = Field(default=None, max_length=4000)
    responsable_id: Optional[int] = None

    @field_validator("etiquetas")
    @classmethod
    def limpiar_etiquetas(cls, valor: Optional[List[str]]) -> Optional[List[str]]:
        if valor is None:
            return None
        limpias: List[str] = []
        vistas = set()
        for etiqueta in valor:
            limpia = " ".join(str(etiqueta).split())
            if not limpia:
                continue
            if len(limpia) > 30:
                raise ValueError("Cada etiqueta puede tener máximo 30 caracteres.")
            if "," in limpia:
                raise ValueError("Las etiquetas no pueden contener comas.")
            clave = limpia.casefold()
            if clave in vistas:
                continue
            vistas.add(clave)
            limpias.append(limpia)
        if len(limpias) > 8:
            raise ValueError("Puedes usar máximo 8 etiquetas.")
        return limpias

    @field_validator("notas_internas")
    @classmethod
    def limpiar_notas(cls, valor: Optional[str]) -> Optional[str]:
        if valor is None:
            return None
        limpio = valor.strip()
        return limpio or None


class FeedbackResponse(BaseModel):
    id: int
    tipo: str
    comentario: str
    contexto: Dict[str, Any]
    estado: str
    prioridad: str
    etiquetas: List[str] = Field(default_factory=list)
    usuario_id: Optional[int] = None
    usuario_nombre: str
    responsable_id: Optional[int] = None
    responsable_nombre: Optional[str] = None
    tiene_captura: bool = False
    captura_mime: Optional[str] = None
    captura_nombre: Optional[str] = None
    notas_internas: Optional[str] = None
    creado_en: datetime
    actualizado_en: datetime
    resuelto_en: Optional[datetime] = None

    @field_validator("etiquetas", mode="before")
    @classmethod
    def convertir_etiquetas(cls, valor):
        if valor is None:
            return []
        if isinstance(valor, str):
            return [parte.strip() for parte in valor.split(",") if parte.strip()]
        return valor

    class Config:
        from_attributes = True
