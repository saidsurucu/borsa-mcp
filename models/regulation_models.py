"""
Fund regulation models for Turkish investment fund compliance.
Contains models for fund regulation guides, legal compliance,
and regulatory documentation.
"""
from pydantic import BaseModel, Field
from typing import Optional

# --- Fund Regulation Model ---

class FonMevzuatSonucu(BaseModel):
    """Fund regulation guide content for legal compliance."""
    baslik: Optional[str] = Field(None, description="Regulation guide title.")
    icerik: Optional[str] = Field(None, description="Complete regulation content in Turkish covering investment fund rules, portfolio limits, fund types, and compliance requirements.")
    dosya_boyutu: Optional[int] = Field(None, description="Content size in characters.")
    son_guncelleme: Optional[str] = Field(None, description="Last update timestamp of the regulation content.")
    kaynak: Optional[str] = Field(None, description="Source file or Python module containing the regulation data.")
    error_message: Optional[str] = Field(None, description="Error message if regulation retrieval failed.")