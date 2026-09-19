from typing import List
from app.research.portfolio_stress.models import PortfolioStressResult
from app.research.portfolio_discovery.models import PortfolioResearchQuestion
from app.research.portfolio_discovery.discovery import PortfolioDiscoveryEngine

class PortfolioDiscoveryService:
    
    def __init__(self):
        self.question_repository: List[PortfolioResearchQuestion] = []
        
    def analyze_stress_result(self, result: PortfolioStressResult) -> PortfolioResearchQuestion:
        q = PortfolioDiscoveryEngine.evaluate(result, self.question_repository)
        self.question_repository.append(q)
        return q
