from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class PreferenceInputs(BaseModel):
    budget_sensitivity: str = Field(default="Medium", description="Low/Medium/High")
    strong_scholarships: bool = False
    research_focused: bool = False
    high_acceptance_chances: bool = False
    top_ranked_only: bool = False


class QueryInputs(BaseModel):
    major: str
    region: str
    degree_level: str
    preferences: PreferenceInputs


class CandidateSchool(BaseModel):
    name: str
    location: str = "Unknown"
    official_website: Optional[str] = None
    sources: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class CollegeResult(BaseModel):
    rank: int
    name: str
    location: str
    program_strength: str
    why_fit: List[str]
    selectivity: str = "Unknown"
    estimated_cost_tier: Optional[str] = None
    official_website: Optional[str] = None
    sources: List[str]


class CollegeCompassResponse(BaseModel):
    query: Dict[str, Any]
    results: List[CollegeResult]
