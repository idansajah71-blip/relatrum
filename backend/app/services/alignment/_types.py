from dataclasses import dataclass


@dataclass
class Candidate:
    requirement: object
    observation: object
    lexical_similarity: float
    fuzzy_similarity: float
    combined_similarity: float = 0.0
